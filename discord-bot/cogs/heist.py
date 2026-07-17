"""
HeistManager — GTA Online Heist Queue System
Commands: /heist_join  /heist_leave  /heist_list  /heist_start  /heist_clear
          /heist_stats

Features
────────
• Persistent Join / Leave buttons on /heist_list (survive bot restarts)
• Auto full-lobby ping: when the 4th player joins the bot immediately pings
  all four players in the channel with a public announcement
• Heist history: /heist_start records a completed heist for every player
  in the queue; /heist_stats shows a per-server leaderboard
• All Discord responses go through _safe_respond() which silently swallows
  dead/expired tokens (dual-gateway-session race protection)
"""

import json
import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands, ui
from discord.ext import commands

logger = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
QUEUE_FILE  = os.path.join(DATA_DIR, "heist_queues.json")
STATS_FILE  = os.path.join(DATA_DIR, "heist_stats.json")
os.makedirs(DATA_DIR, exist_ok=True)

MAX_PLAYERS = 4

# ── Colours ───────────────────────────────────────────────────────────────────
GOLD      = 0xC8A951
RED       = 0xC0392B
GREEN     = 0x2ECC71
DARK_GREY = 0x2C2C2C
PURPLE    = 0x9B59B6


# ─────────────────────────────────────────────────────────────────────────────
# Safe interaction helper
# ─────────────────────────────────────────────────────────────────────────────

async def _safe_respond(
    interaction: discord.Interaction,
    *,
    content: str = None,
    embed: discord.Embed = None,
    view: discord.ui.View = None,
    ephemeral: bool = False,
) -> None:
    """Send a response, silently dropping dead/already-claimed tokens."""
    kwargs = {}
    if content is not None:
        kwargs["content"] = content
    if embed is not None:
        kwargs["embed"] = embed
    if view is not None:
        kwargs["view"] = view
    if ephemeral:
        kwargs["ephemeral"] = True

    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except (discord.NotFound, discord.HTTPException) as exc:
        logger.debug("Interaction response silently dropped (%s): %s", type(exc).__name__, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Queue persistence
# ─────────────────────────────────────────────────────────────────────────────

def _load_queues() -> dict:
    try:
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_queues(data: dict) -> None:
    with open(QUEUE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _guild_queue(data: dict, guild_id: int) -> dict:
    key = str(guild_id)
    if key not in data:
        data[key] = {
            "heist_name":  None,
            "players":     [],
            "max_players": MAX_PLAYERS,
            "status":      "open",
        }
    return data[key]


# ─────────────────────────────────────────────────────────────────────────────
# Stats persistence
# ─────────────────────────────────────────────────────────────────────────────

def _load_stats() -> dict:
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_stats(stats: dict) -> None:
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def _record_heist(stats: dict, guild_id: int, players: list) -> None:
    """Increment each player's completed-heist counter for this guild."""
    key = str(guild_id)
    if key not in stats:
        stats[key] = {}
    for p in players:
        uid = str(p["id"])
        if uid not in stats[key]:
            stats[key][uid] = {"name": p["name"], "heists": 0}
        stats[key][uid]["heists"] += 1
        stats[key][uid]["name"] = p["name"]   # refresh display name each time


# ─────────────────────────────────────────────────────────────────────────────
# Full-lobby auto-ping
# ─────────────────────────────────────────────────────────────────────────────

async def _notify_full_lobby(
    channel: discord.TextChannel,
    queue: dict,
    guild: discord.Guild,
) -> None:
    """
    Send a PUBLIC channel message pinging all crew members the instant the
    4th player joins.  Called from both the slash-command and button paths.
    """
    name     = queue["heist_name"] or "GTA Online Heist"
    players  = queue["players"]
    max_p    = queue["max_players"]
    mentions = " ".join(f"<@{p['id']}>" for p in players)

    embed = discord.Embed(
        title="🚨  CREW ASSEMBLED — LOBBY IS FULL",
        description=(
            f"The **{name}** crew is locked in.\n"
            "Everyone send an invite and **DO NOT back out**."
        ),
        colour=RED,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name=f"👥  Your Crew  ({len(players)}/{max_p})",
        value="\n".join(
            f"`[{i + 1}]` <@{p['id']}> — **{p['name']}**"
            for i, p in enumerate(players)
        ),
        inline=False,
    )
    embed.add_field(name="📡  Status",    value="🔴  FULL",                             inline=True)
    embed.add_field(name="⚡  Next Step", value="Admin: use `/heist_start` to launch",  inline=True)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(
        text=f"{guild.name}  •  GTA Heist Queue",
        icon_url=guild.icon.url if guild.icon else None,
    )

    try:
        await channel.send(content=mentions, embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Could not send full-lobby notification: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Embed builders
# ─────────────────────────────────────────────────────────────────────────────

def _queue_embed(queue: dict, guild: discord.Guild) -> discord.Embed:
    players = queue["players"]
    max_p   = queue["max_players"]
    filled  = len(players)
    is_full = queue["status"] == "full"
    name    = queue["heist_name"] or "GTA Online Heist"
    colour  = RED if is_full else GOLD

    embed = discord.Embed(
        title=f"🎯  {name}",
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )

    slots = ""
    for i in range(max_p):
        if i < filled:
            p = players[i]
            slots += f"`[{i + 1}]` <@{p['id']}> — **{p['name']}**\n"
        else:
            slots += f"`[{i + 1}]` ─ *Empty slot*\n"

    embed.add_field(name=f"👥  Crew  ({filled}/{max_p})", value=slots, inline=False)
    embed.add_field(name="📡  Lobby Status", value="🔴 FULL" if is_full else "🟢 OPEN", inline=True)
    embed.add_field(name="🎮  Platform",     value="GTA Online",                        inline=True)
    embed.add_field(name="💰  Max Players",  value=str(max_p),                          inline=True)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(
        text=f"{guild.name}  •  GTA Heist Queue",
        icon_url=guild.icon.url if guild.icon else None,
    )
    return embed


def _simple_embed(title: str, description: str, colour: int) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Shared join / leave logic (pure — no Discord I/O)
# Returns (success: bool, feedback: str)
# ─────────────────────────────────────────────────────────────────────────────

def _do_join(
    data: dict,
    guild_id: int,
    user_id: int,
    display_name: str,
    heist_name: str = None,
) -> tuple[bool, str]:
    queue = _guild_queue(data, guild_id)

    if heist_name and queue["heist_name"] and heist_name.strip() != queue["heist_name"]:
        pass   # silently keep existing name on the button path
    elif heist_name:
        queue["heist_name"] = heist_name.strip()

    if not queue["heist_name"]:
        queue["heist_name"] = "GTA Online Heist"

    if any(p["id"] == user_id for p in queue["players"]):
        return False, "⚠️ You're already in the queue, criminal. Sit tight."

    if len(queue["players"]) >= queue["max_players"]:
        return False, (
            f"🔴 The lobby for **{queue['heist_name']}** is full "
            f"({queue['max_players']}/{queue['max_players']}). Try again next time."
        )

    queue["players"].append({
        "id":        user_id,
        "name":      display_name,
        "joined_at": datetime.now(timezone.utc).isoformat(),
    })

    if len(queue["players"]) >= queue["max_players"]:
        queue["status"] = "full"

    _save_queues(data)
    return True, ""


def _do_leave(data: dict, guild_id: int, user_id: int) -> tuple[bool, str]:
    queue  = _guild_queue(data, guild_id)
    before = len(queue["players"])
    queue["players"] = [p for p in queue["players"] if p["id"] != user_id]

    if len(queue["players"]) == before:
        return False, "⚠️ You're not in the queue."

    if queue["status"] == "full":
        queue["status"] = "open"

    _save_queues(data)
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# Persistent UI View
# ─────────────────────────────────────────────────────────────────────────────

class HeistView(ui.View):
    """
    Persistent Join / Leave buttons attached to every /heist_list message.
    timeout=None + stable custom_ids = buttons survive bot restarts.
    A FRESH instance must be created for each outgoing send; the bot.add_view()
    instance is only for routing interactions from old messages after restart.
    """

    def __init__(self, manager: "HeistManager"):
        super().__init__(timeout=None)
        self._mgr = manager

    # ── Join ─────────────────────────────────────────────────────────────────

    @ui.button(
        label="Join Heist",
        style=discord.ButtonStyle.success,
        emoji="🎯",
        custom_id="heist_view:join",
    )
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        ok, msg = _do_join(
            self._mgr._queues,
            interaction.guild_id,
            interaction.user.id,
            interaction.user.display_name,
        )

        queue = _guild_queue(self._mgr._queues, interaction.guild_id)
        just_filled = ok and queue["status"] == "full"

        if ok:
            feedback = (
                f"✅ **{interaction.user.display_name}** joined — "
                f"spot **#{len(queue['players'])}** of {queue['max_players']}."
            )
            if just_filled:
                feedback += "\n🔴 **Lobby is now full!** The crew is being notified."
        else:
            feedback = msg

        await self._refresh_list_message(interaction, feedback, ok)

        # Fire the public ping AFTER the interaction is acknowledged
        if just_filled:
            await _notify_full_lobby(interaction.channel, queue, interaction.guild)

    # ── Leave ────────────────────────────────────────────────────────────────

    @ui.button(
        label="Leave Heist",
        style=discord.ButtonStyle.danger,
        emoji="👋",
        custom_id="heist_view:leave",
    )
    async def leave_button(self, interaction: discord.Interaction, button: ui.Button):
        ok, msg = _do_leave(
            self._mgr._queues,
            interaction.guild_id,
            interaction.user.id,
        )

        if ok:
            feedback = f"👋 **{interaction.user.display_name}** left the queue. Slot freed."
        else:
            feedback = msg

        await self._refresh_list_message(interaction, feedback, ok)

    # ── Shared refresh ───────────────────────────────────────────────────────

    async def _refresh_list_message(
        self,
        interaction: discord.Interaction,
        feedback: str,
        success: bool,
    ) -> None:
        """
        Defer ephemerally → edit the original embed in-place → send private
        feedback to the user who clicked.
        """
        queue         = _guild_queue(self._mgr._queues, interaction.guild_id)
        updated_embed = _queue_embed(queue, interaction.guild)

        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return   # token already dead

        try:
            await interaction.message.edit(embed=updated_embed, view=self)
        except (discord.NotFound, discord.HTTPException, discord.Forbidden) as exc:
            logger.debug("Could not edit heist list message: %s", exc)

        try:
            fb_embed = _simple_embed(
                "✅ Done" if success else "⚠️ Notice",
                feedback,
                GREEN if success else RED,
            )
            await interaction.followup.send(embed=fb_embed, ephemeral=True)
        except (discord.NotFound, discord.HTTPException) as exc:
            logger.debug("Could not send button followup: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class HeistManager(commands.Cog):
    """GTA Online Heist Queue — join, leave, stats, and lobby management."""

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self._queues = _load_queues()
        self._stats  = _load_stats()
        # Register persistent view for restart recovery (NOT reused for sends)
        bot.add_view(HeistView(self))

    # ── /heist_join ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_join",
        description="Join the GTA heist queue. Optionally name the heist.",
    )
    @app_commands.describe(heist_name="Name of the heist (e.g. 'The Doomsday Heist'). Optional.")
    @app_commands.guild_only()
    async def heist_join(self, interaction: discord.Interaction, heist_name: str = None):
        ok, msg = _do_join(
            self._queues,
            interaction.guild_id,
            interaction.user.id,
            interaction.user.display_name,
            heist_name,
        )
        queue       = _guild_queue(self._queues, interaction.guild_id)
        just_filled = ok and queue["status"] == "full"

        if not ok:
            await _safe_respond(interaction, content=msg, ephemeral=True)
            return

        pos   = len(queue["players"])
        embed = _simple_embed(
            "✅  Added to the Crew",
            (
                f"**{interaction.user.display_name}** is in — spot **#{pos}** of "
                f"{queue['max_players']} for **{queue['heist_name']}**."
            ),
            GREEN,
        )
        if just_filled:
            embed.add_field(
                name="🔴 Lobby Full",
                value="The crew is complete — notifying everyone now!",
                inline=False,
            )
        await _safe_respond(interaction, embed=embed, ephemeral=True)

        if just_filled:
            await _notify_full_lobby(interaction.channel, queue, interaction.guild)

    # ── /heist_leave ─────────────────────────────────────────────────────────

    @app_commands.command(name="heist_leave", description="Leave the current GTA heist queue.")
    @app_commands.guild_only()
    async def heist_leave(self, interaction: discord.Interaction):
        ok, msg = _do_leave(self._queues, interaction.guild_id, interaction.user.id)

        if not ok:
            await _safe_respond(interaction, content=msg, ephemeral=True)
            return

        queue = _guild_queue(self._queues, interaction.guild_id)
        await _safe_respond(
            interaction,
            embed=_simple_embed(
                "👋  Left the Queue",
                f"**{interaction.user.display_name}** bailed on **{queue['heist_name']}**. Slot freed.",
                DARK_GREY,
            ),
            ephemeral=True,
        )

    # ── /heist_list ──────────────────────────────────────────────────────────

    @app_commands.command(name="heist_list", description="Display the current GTA heist queue.")
    @app_commands.guild_only()
    async def heist_list(self, interaction: discord.Interaction):
        queue = _guild_queue(self._queues, interaction.guild_id)
        # Always render embed + buttons regardless of lobby state.
        # Fresh HeistView instance per send — do not reuse the bot.add_view() instance.
        await _safe_respond(
            interaction,
            embed=_queue_embed(queue, interaction.guild),
            view=HeistView(self),
        )

    # ── /heist_start ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_start",
        description="[Admin] Confirm the heist launched — records stats for all queued players.",
    )
    @app_commands.describe(heist_name="Override the heist name for the announcement. Optional.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def heist_start(self, interaction: discord.Interaction, heist_name: str = None):
        queue = _guild_queue(self._queues, interaction.guild_id)

        if heist_name:
            queue["heist_name"] = heist_name.strip()
        if not queue["heist_name"]:
            queue["heist_name"] = "GTA Online Heist"

        queue["status"] = "full"
        _save_queues(self._queues)

        players  = queue["players"]
        max_p    = queue["max_players"]
        name     = queue["heist_name"]
        mentions = "  ".join(f"<@{p['id']}>" for p in players) if players else "*No players registered*"

        # ── Record completed heist in stats ──────────────────────────────────
        if players:
            _record_heist(self._stats, interaction.guild_id, players)
            _save_stats(self._stats)

        embed = discord.Embed(
            title=f"🚨  HEIST LAUNCHED  —  {name}",
            description=(
                "The crew is assembled. Everyone invite up and **DO NOT back out**.\n"
                "Failure is not an option, gentlemen."
            ),
            colour=RED,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name=f"👥  Crew  ({len(players)}/{max_p})",
            value="\n".join(
                f"`[{i + 1}]` <@{p['id']}> — **{p['name']}**" for i, p in enumerate(players)
            ) or "*No confirmed players*",
            inline=False,
        )
        embed.add_field(name="📡  Status",        value="🔴  LAUNCHED",  inline=True)
        embed.add_field(name="🎮  Platform",      value="GTA Online",    inline=True)
        embed.add_field(name="📣  Crew Mentions", value=mentions,        inline=False)

        if players:
            embed.add_field(
                name="📊  Stats Updated",
                value=f"Heist recorded for **{len(players)}** player{'s' if len(players) != 1 else ''}. "
                      "Check `/heist_stats` for the leaderboard.",
                inline=False,
            )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"Launched by {interaction.user.display_name}  •  GTA Heist Queue")

        await _safe_respond(interaction, embed=embed)

    # ── /heist_stats ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_stats",
        description="Show the top heist participants in this server.",
    )
    @app_commands.guild_only()
    async def heist_stats(self, interaction: discord.Interaction):
        guild_stats = self._stats.get(str(interaction.guild_id), {})

        if not guild_stats:
            await _safe_respond(
                interaction,
                embed=_simple_embed(
                    "📊  Heist Leaderboard",
                    "No heists completed yet.\nUse `/heist_start` after a successful run to record it!",
                    GOLD,
                ),
            )
            return

        # Sort descending by count, cap at top 10
        ranked = sorted(
            guild_stats.items(),
            key=lambda kv: kv[1]["heists"],
            reverse=True,
        )[:10]

        medals      = ["🥇", "🥈", "🥉"]
        board_lines = []
        for i, (uid, entry) in enumerate(ranked):
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            count  = entry["heists"]
            noun   = "heist" if count == 1 else "heists"
            board_lines.append(f"{prefix}  **{entry['name']}** — {count} {noun}")

        total_runs    = sum(v["heists"] for v in guild_stats.values())
        total_players = len(guild_stats)

        embed = discord.Embed(
            title="📊  Heist Leaderboard",
            description="Top crew members by completed heists on this server",
            colour=GOLD,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="🏆  Rankings",
            value="\n".join(board_lines),
            inline=False,
        )
        embed.add_field(
            name="🎯  Total Heist Runs",
            value=str(total_runs),
            inline=True,
        )
        embed.add_field(
            name="👥  Unique Criminals",
            value=str(total_players),
            inline=True,
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(
            text=f"{interaction.guild.name}  •  GTA Heist History",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )

        await _safe_respond(interaction, embed=embed)

    # ── /heist_clear ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_clear",
        description="[Admin] Clear the heist queue and reset for a new session.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def heist_clear(self, interaction: discord.Interaction):
        self._queues[str(interaction.guild_id)] = {
            "heist_name":  None,
            "players":     [],
            "max_players": MAX_PLAYERS,
            "status":      "open",
        }
        _save_queues(self._queues)

        await _safe_respond(
            interaction,
            embed=_simple_embed(
                "🗑️  Queue Cleared",
                "The heist queue has been wiped. Use `/heist_join` to start filling a new lobby.",
                DARK_GREY,
            ),
            ephemeral=True,
        )


# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(HeistManager(bot))
