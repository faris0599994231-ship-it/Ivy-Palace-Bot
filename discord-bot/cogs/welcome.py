import json
import logging
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "welcome.json")

DEFAULT_MESSAGE = (
    "👋 Welcome to **{server}**, {user}! "
    "You're our **{count}** member. Enjoy your stay!"
)

# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

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


def _guild_cfg(data: dict, guild_id: int) -> dict:
    key = str(guild_id)
    if key not in data:
        data[key] = {
            "enabled": False,
            "channel_id": None,
            "message": DEFAULT_MESSAGE,
        }
    return data[key]


def _format_message(template: str, member: discord.Member) -> str:
    return template.format(
        user=member.mention,
        username=member.name,
        server=member.guild.name,
        count=member.guild.member_count,
    )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Welcome(commands.Cog):
    """Welcome message system — greet new members automatically."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._data: dict = _load()

    # ------------------------------------------------------------------
    # Event listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = _guild_cfg(self._data, member.guild.id)
        if not cfg["enabled"] or not cfg["channel_id"]:
            return
        channel = member.guild.get_channel(cfg["channel_id"])
        if channel is None:
            logger.warning(
                f"Welcome channel {cfg['channel_id']} not found in {member.guild.id}"
            )
            return
        embed = self._build_embed(member, cfg["message"])
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Cannot send welcome message in {channel.id} — missing permissions.")

    # ------------------------------------------------------------------
    # Slash command group
    # ------------------------------------------------------------------

    welcome_group = app_commands.Group(
        name="welcome",
        description="Configure the welcome message system.",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @welcome_group.command(name="channel", description="Set the channel where welcome messages are sent.")
    @app_commands.describe(channel="The text channel to send welcome messages in.")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = _guild_cfg(self._data, interaction.guild.id)
        cfg["channel_id"] = channel.id
        _save(self._data)
        await interaction.response.send_message(
            f"✅ Welcome channel set to {channel.mention}.", ephemeral=True
        )

    @welcome_group.command(name="message", description="Set the welcome message template.")
    @app_commands.describe(
        message=(
            "Message text. Use {user} for mention, {username} for name, "
            "{server} for server name, {count} for member count."
        )
    )
    async def set_message(self, interaction: discord.Interaction, message: str):
        cfg = _guild_cfg(self._data, interaction.guild.id)
        cfg["message"] = message
        _save(self._data)
        await interaction.response.send_message(
            f"✅ Welcome message updated.\n\n**Preview:**\n{self._preview(message, interaction.user, interaction.guild)}",
            ephemeral=True,
        )

    @welcome_group.command(name="toggle", description="Enable or disable welcome messages.")
    async def toggle(self, interaction: discord.Interaction):
        cfg = _guild_cfg(self._data, interaction.guild.id)
        cfg["enabled"] = not cfg["enabled"]
        _save(self._data)
        state = "✅ enabled" if cfg["enabled"] else "⏸️ disabled"
        await interaction.response.send_message(
            f"Welcome messages are now **{state}**.", ephemeral=True
        )

    @welcome_group.command(name="test", description="Send a test welcome message to the configured channel.")
    async def test(self, interaction: discord.Interaction):
        cfg = _guild_cfg(self._data, interaction.guild.id)
        if not cfg["channel_id"]:
            await interaction.response.send_message(
                "❌ No welcome channel set. Use `/welcome channel` first.", ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(cfg["channel_id"])
        if channel is None:
            await interaction.response.send_message(
                "❌ The configured channel no longer exists. Please set a new one.", ephemeral=True
            )
            return
        embed = self._build_embed(interaction.user, cfg["message"])
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(
                f"✅ Test welcome message sent to {channel.mention}.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}.", ephemeral=True
            )

    @welcome_group.command(name="view", description="Show the current welcome message settings.")
    async def view(self, interaction: discord.Interaction):
        cfg = _guild_cfg(self._data, interaction.guild.id)
        channel = (
            interaction.guild.get_channel(cfg["channel_id"]).mention
            if cfg["channel_id"]
            else "*not set*"
        )
        state = "✅ Enabled" if cfg["enabled"] else "⏸️ Disabled"
        embed = discord.Embed(
            title="Welcome Message Settings",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Status", value=state, inline=True)
        embed.add_field(name="Channel", value=channel, inline=True)
        embed.add_field(name="Message Template", value=f"```\n{cfg['message']}\n```", inline=False)
        embed.add_field(
            name="Placeholders",
            value="`{user}` mention · `{username}` name · `{server}` server · `{count}` member count",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome_group.command(name="reset", description="Reset the welcome message to the default template.")
    async def reset(self, interaction: discord.Interaction):
        cfg = _guild_cfg(self._data, interaction.guild.id)
        cfg["message"] = DEFAULT_MESSAGE
        _save(self._data)
        await interaction.response.send_message(
            "✅ Welcome message reset to the default template.", ephemeral=True
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_embed(self, member: discord.Member | discord.User, template: str) -> discord.Embed:
        guild = getattr(member, "guild", None)
        text = template.format(
            user=member.mention,
            username=member.name,
            server=guild.name if guild else "this server",
            count=guild.member_count if guild else "?",
        )
        embed = discord.Embed(
            description=text,
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if guild and guild.icon:
            embed.set_footer(text=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_footer(text=guild.name if guild else "Welcome")
        return embed

    def _preview(self, template: str, user: discord.User, guild: discord.Guild) -> str:
        return template.format(
            user=user.mention,
            username=user.name,
            server=guild.name,
            count=guild.member_count,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
