"""
HeistManager — GTA Online Heist Queue System
Commands: /heist_join  /heist_leave  /heist_list  /heist_start  /heist_clear

Join/Leave logic is shared between slash commands and persistent UI buttons.
The HeistView (timeout=None, stable custom_ids) is registered with the bot
on cog load so buttons survive bot restarts.

All Discord responses go through _safe_respond(), which silently ignores
dead/expired tokens that occur when the dev and production bots are both
connected on the same token simultaneously.
"""

import json
import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands, ui
from discord.ext import commands

logger = logging.getLogger(__name__)

DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_FILE = os.path.join(DATA_DIR, "heist_queues.json")
os.makedirs(DATA_DIR, exist_ok=True)

MAX_PLAYERS = 4

# ── Colours ───────────────────────────────────────────────────────────────────
GOLD      = 0xC8A951
RED       = 0xC0392B
GREEN     = 0x2ECC71
DARK_GREY = 0x2C2C2C


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
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
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
# Embed builders
# ─────────────────────────────────────────────────────────────────────────────

def _queue_embed(queue: dict, guild: discord.Guild) -> discord.Embed:
    players  = queue["players"]
    max_p    = queue["max_players"]
    filled   = len(players)
    is_full  = queue["status"] == "full"
    name     = queue["heist_name"] or "GTA Online Heist"
    colour   = RED if is_full else GOLD

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
# Shared join / leave logic
# Returns a tuple: (success: bool, feedback_message: str)
# ─────────────────────────────────────────────────────────────────────────────

def _do_join(data: dict, guild_id: int, user_id: int, display_name: str,
             heist_name: str = None) -> tuple[bool, str]:
    queue = _guild_queue(data, guild_id)

    if heist_name and queue["heist_name"] and heist_name.strip() != queue["heist_name"]:
        # Non-admin name conflicts are resolved by ignoring the new name (button path)
        pass
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

    _save(data)
    return True, ""


def _do_leave(data: dict, guild_id: int, user_id: int) -> tuple[bool, str]:
    queue  = _guild_queue(data, guild_id)
    before = len(queue["players"])
    queue["players"] = [p for p in queue["players"] if p["id"] != user_id]

    if len(queue["players"]) == before:
        return False, "⚠️ You're not in the queue."

    if queue["status"] == "full":
        queue["status"] = "open"

    _save(data)
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# Persistent UI View
# ─────────────────────────────────────────────────────────────────────────────

class HeistView(ui.View):
    """
    Persistent Join / Leave buttons attached to /heist_list messages.
    timeout=None + stable custom_ids means buttons keep working after restarts.
    The cog stores a reference to HeistManager so button callbacks share data.
    """

    def __init__(self, manager: "HeistManager"):
        super().__init__(timeout=None)
        self._mgr = manager

    @ui.button(
        label="Join Heist",
        style=discord.ButtonStyle.success,
        emoji="🎯",
        custom_id="heist_view:join",
    )
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        ok, msg = _do_join(
            self._mgr._data,
            interaction.guild_id,
            interaction.user.id,
            interaction.user.display_name,
        )

        queue = _guild_queue(self._mgr._data, interaction.guild_id)

        if ok:
            feedback = (
                f"✅ **{interaction.user.display_name}** joined — "
                f"spot **#{len(queue['players'])}** of {queue['max_players']}."
            )
            if queue["status"] == "full":
                feedback += "\n🔴 **Lobby is now full!** Use `/heist_start` to launch."
        else:
            feedback = msg

        # Update the public embed in-place, then ack ephemerally
        await self._refresh_list_message(interaction, feedback, ok)

    @ui.button(
        label="Leave Heist",
        style=discord.ButtonStyle.danger,
        emoji="👋",
        custom_id="heist_view:leave",
    )
    async def leave_button(self, interaction: discord.Interaction, button: ui.Button):
        ok, msg = _do_leave(
            self._mgr._data,
            interaction.guild_id,
            interaction.user.id,
        )

        if ok:
            feedback = f"👋 **{interaction.user.display_name}** left the queue. Slot freed."
        else:
            feedback = msg

        await self._refresh_list_message(interaction, feedback, ok)

    async def _refresh_list_message(
        self,
        interaction: discord.Interaction,
        feedback: str,
        success: bool,
    ):
        """
        Edit the original /heist_list message with a fresh embed, then send
        an ephemeral acknowledgement so the button click has visible feedback.
        """
        queue = _guild_queue(self._mgr._data, interaction.guild_id)
        updated_embed = _queue_embed(queue, interaction.guild)

        # Acknowledge the button click so Discord knows we handled it
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return  # token already dead — nothing to do

        # Update the embed on the original message
        try:
            await interaction.message.edit(embed=updated_embed, view=self)
        except (discord.NotFound, discord.HTTPException, discord.Forbidden) as exc:
            logger.debug("Could not edit heist list message: %s", exc)

        # Send ephemeral feedback to the person who clicked
        try:
            colour = GREEN if success else RED
            fb_embed = _simple_embed(
                "✅ Done" if success else "⚠️ Notice",
                feedback,
                colour,
            )
            await interaction.followup.send(embed=fb_embed, ephemeral=True)
        except (discord.NotFound, discord.HTTPException) as exc:
            logger.debug("Could not send button followup: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class HeistManager(commands.Cog):
    """GTA Online Heist Queue — join, leave, and manage lobby sign-ups."""

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self._data = _load()
        # Register a persistent view so Discord.py can route button interactions
        # from OLD messages back to this cog after a restart.
        # Do NOT reuse this instance for outgoing messages — create a fresh
        # HeistView(self) for each send so Discord receives the component payload.
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
            self._data,
            interaction.guild_id,
            interaction.user.id,
            interaction.user.display_name,
            heist_name,
        )
        queue = _guild_queue(self._data, interaction.guild_id)

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
        if queue["status"] == "full":
            embed.add_field(
                name="🔴 Lobby Full",
                value="The crew is complete! Use `/heist_start` to announce the launch.",
                inline=False,
            )
        await _safe_respond(interaction, embed=embed, ephemeral=True)

    # ── /heist_leave ─────────────────────────────────────────────────────────

    @app_commands.command(name="heist_leave", description="Leave the current GTA heist queue.")
    @app_commands.guild_only()
    async def heist_leave(self, interaction: discord.Interaction):
        ok, msg = _do_leave(self._data, interaction.guild_id, interaction.user.id)

        if not ok:
            await _safe_respond(interaction, content=msg, ephemeral=True)
            return

        queue = _guild_queue(self._data, interaction.guild_id)
        await _safe_respond(
            interaction,
            embed=_simple_embed(
                "👋  Left the Queue",
                f"**{interaction.user.display_name}** has bailed on **{queue['heist_name']}**. Slot freed.",
                DARK_GREY,
            ),
            ephemeral=True,
        )

    # ── /heist_list ──────────────────────────────────────────────────────────

    @app_commands.command(name="heist_list", description="Display the current GTA heist queue.")
    @app_commands.guild_only()
    async def heist_list(self, interaction: discord.Interaction):
        queue = _guild_queue(self._data, interaction.guild_id)
        # Always render the embed + buttons regardless of lobby state.
        # A fresh HeistView instance is created per send so Discord includes
        # the component payload in the message (the bot.add_view instance is
        # for restart-recovery only and must not be reused for outgoing sends).
        await _safe_respond(
            interaction,
            embed=_queue_embed(queue, interaction.guild),
            view=HeistView(self),
        )

    # ── /heist_start ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_start",
        description="[Admin] Announce that the heist lobby is full and ready to launch.",
    )
    @app_commands.describe(heist_name="Override the heist name for the announcement. Optional.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def heist_start(self, interaction: discord.Interaction, heist_name: str = None):
        queue = _guild_queue(self._data, interaction.guild_id)

        if heist_name:
            queue["heist_name"] = heist_name.strip()
        if not queue["heist_name"]:
            queue["heist_name"] = "GTA Online Heist"

        queue["status"] = "full"
        _save(self._data)

        players  = queue["players"]
        max_p    = queue["max_players"]
        name     = queue["heist_name"]
        mentions = "  ".join(f"<@{p['id']}>" for p in players) if players else "*No players registered*"

        embed = discord.Embed(
            title=f"🚨  HEIST LOBBY FULL  —  {name}",
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
        embed.add_field(name="📡  Status",        value="🔴  FULL — Invite sent", inline=True)
        embed.add_field(name="🎮  Platform",      value="GTA Online",             inline=True)
        embed.add_field(name="📣  Crew Mentions", value=mentions,                 inline=False)

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"Launched by {interaction.user.display_name}  •  GTA Heist Queue")

        await _safe_respond(interaction, embed=embed)

    # ── /heist_clear ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_clear",
        description="[Admin] Clear the heist queue and reset for a new session.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def heist_clear(self, interaction: discord.Interaction):
        self._data[str(interaction.guild_id)] = {
            "heist_name":  None,
            "players":     [],
            "max_players": MAX_PLAYERS,
            "status":      "open",
        }
        _save(self._data)

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
