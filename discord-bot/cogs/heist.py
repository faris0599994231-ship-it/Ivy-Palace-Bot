"""
HeistManager — GTA Online Heist Queue System
Commands: /heist_join  /heist_leave  /heist_list  /heist_start  /heist_clear

No defer() is used — all operations are synchronous JSON I/O that completes
well within Discord's 3-second response window, so we respond in one shot.
This avoids "already acknowledged" crashes when the restart loop briefly runs
two bot instances at the same time.
"""

import json
import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "heist_queues.json")

# GTA heists are 2–4 players; 4 is the standard max.
MAX_PLAYERS = 4

# Colours
GOLD      = 0xC8A951   # GTA money gold — main embeds
RED       = 0xC0392B   # queue full / errors
GREEN     = 0x2ECC71   # success confirmations
DARK_GREY = 0x2C2C2C   # neutral / cleared

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
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _guild_queue(data: dict, guild_id: int) -> dict:
    """Return the queue dict for this guild, creating it if absent."""
    key = str(guild_id)
    if key not in data:
        data[key] = {
            "heist_name":  None,
            "players":     [],       # list of {id, name, joined_at}
            "max_players": MAX_PLAYERS,
            "status":      "open",   # "open" | "full"
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

    status_icon = "🔴 FULL" if is_full else "🟢 OPEN"
    colour      = RED       if is_full else GOLD

    embed = discord.Embed(
        title=f"🎯  {name}",
        colour=colour,
        timestamp=datetime.now(timezone.utc),
    )

    slots_text = ""
    for i in range(max_p):
        if i < filled:
            p = players[i]
            slots_text += f"`[{i + 1}]` <@{p['id']}> — **{p['name']}**\n"
        else:
            slots_text += f"`[{i + 1}]` ─ *Empty slot*\n"

    embed.add_field(name=f"👥  Crew  ({filled}/{max_p})", value=slots_text, inline=False)
    embed.add_field(name="📡  Lobby Status", value=status_icon,  inline=True)
    embed.add_field(name="🎮  Platform",     value="GTA Online", inline=True)
    embed.add_field(name="💰  Max Players",  value=str(max_p),   inline=True)

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
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class HeistManager(commands.Cog):
    """GTA Online Heist Queue — join, leave, and manage lobby sign-ups."""

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self._data = _load()

    # ── /heist_join ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_join",
        description="Join the GTA heist queue. Optionally name the heist.",
    )
    @app_commands.describe(heist_name="Name of the heist (e.g. 'The Doomsday Heist'). Optional.")
    @app_commands.guild_only()
    async def heist_join(
        self,
        interaction: discord.Interaction,
        heist_name: str = None,
    ):
        queue = _guild_queue(self._data, interaction.guild.id)

        # Only admins may switch an in-progress queue to a different heist name
        if (
            heist_name
            and queue["heist_name"]
            and heist_name.strip() != queue["heist_name"]
            and not interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                f"❌ A queue for **{queue['heist_name']}** is already active. "
                "Ask an admin to `/heist_clear` before starting a new one.",
                ephemeral=True,
            )
            return

        # Set or keep the heist name
        if heist_name:
            queue["heist_name"] = heist_name.strip()
        if not queue["heist_name"]:
            queue["heist_name"] = "GTA Online Heist"

        uid = interaction.user.id

        # Already in queue?
        if any(p["id"] == uid for p in queue["players"]):
            await interaction.response.send_message(
                "⚠️ You're already in the queue, criminal. Sit tight.",
                ephemeral=True,
            )
            return

        # Queue full?
        if len(queue["players"]) >= queue["max_players"]:
            await interaction.response.send_message(
                f"🔴 The lobby for **{queue['heist_name']}** is full "
                f"({queue['max_players']}/{queue['max_players']}). Try again next time.",
                ephemeral=True,
            )
            return

        queue["players"].append({
            "id":        uid,
            "name":      interaction.user.display_name,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        })

        # Auto-mark full when last slot fills
        if len(queue["players"]) >= queue["max_players"]:
            queue["status"] = "full"

        _save(self._data)

        pos = len(queue["players"])
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /heist_leave ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_leave",
        description="Leave the current GTA heist queue.",
    )
    @app_commands.guild_only()
    async def heist_leave(self, interaction: discord.Interaction):
        queue  = _guild_queue(self._data, interaction.guild.id)
        uid    = interaction.user.id
        before = len(queue["players"])
        queue["players"] = [p for p in queue["players"] if p["id"] != uid]

        if len(queue["players"]) == before:
            await interaction.response.send_message(
                "⚠️ You're not in the queue.",
                ephemeral=True,
            )
            return

        # Re-open a freed slot
        if queue["status"] == "full":
            queue["status"] = "open"

        _save(self._data)

        embed = _simple_embed(
            "👋  Left the Queue",
            (
                f"**{interaction.user.display_name}** has bailed on "
                f"**{queue['heist_name']}**. Slot freed."
            ),
            DARK_GREY,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /heist_list ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_list",
        description="Display the current GTA heist queue.",
    )
    @app_commands.guild_only()
    async def heist_list(self, interaction: discord.Interaction):
        queue = _guild_queue(self._data, interaction.guild.id)

        if not queue["heist_name"] and not queue["players"]:
            await interaction.response.send_message(
                "📋 No active heist queue. Use `/heist_join` to start one!",
            )
            return

        embed = _queue_embed(queue, interaction.guild)
        await interaction.response.send_message(embed=embed)

    # ── /heist_start ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_start",
        description="[Admin] Announce that the heist lobby is full and ready to launch.",
    )
    @app_commands.describe(heist_name="Override the heist name for the announcement. Optional.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def heist_start(
        self,
        interaction: discord.Interaction,
        heist_name: str = None,
    ):
        queue = _guild_queue(self._data, interaction.guild.id)

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
                f"`[{i + 1}]` <@{p['id']}> — **{p['name']}**"
                for i, p in enumerate(players)
            ) or "*No confirmed players*",
            inline=False,
        )
        embed.add_field(name="📡  Status",      value="🔴  FULL — Invite sent", inline=True)
        embed.add_field(name="🎮  Platform",    value="GTA Online",             inline=True)
        embed.add_field(name="📣  Crew Mentions", value=mentions,               inline=False)

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"Launched by {interaction.user.display_name}  •  GTA Heist Queue")

        await interaction.response.send_message(embed=embed)

    # ── /heist_clear ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="heist_clear",
        description="[Admin] Clear the heist queue and reset for a new session.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def heist_clear(self, interaction: discord.Interaction):
        self._data[str(interaction.guild.id)] = {
            "heist_name":  None,
            "players":     [],
            "max_players": MAX_PLAYERS,
            "status":      "open",
        }
        _save(self._data)

        embed = _simple_embed(
            "🗑️  Queue Cleared",
            "The heist queue has been wiped. Use `/heist_join` to start filling a new lobby.",
            DARK_GREY,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(HeistManager(bot))
