"""
TicketSystem — Support Ticket Management
Commands: /ticket_setup

Workflow
────────
1. Admin runs /ticket_setup → embed with "Open Ticket" button posted in channel
2. User clicks "Open Ticket" → private ticket-{username} channel created under
   the "Tickets" category (created automatically if absent)
3. Only the opener and the "Support Team" role may view the channel
4. "Close Ticket" button in the welcome message → ephemeral confirmation prompt
5. Confirmed → full transcript saved as .txt → sent to #ticket-logs → channel deleted

Persistence
───────────
• Open tickets tracked in data/tickets.json  {guild_id: {user_id: channel_id}}
• TicketOpenView  (custom_id ticket:create) and
  TicketCloseView (custom_id ticket:close) are registered as persistent views
  so buttons survive bot restarts

Error handling
──────────────
• Duplicate ticket prevention (one open ticket per user)
• Missing "Support Team" role → permissions applied for opener only
• Bot missing Manage Channels → graceful ephemeral error
• All Discord responses go through _safe_respond() for dead-token safety
"""

import io
import json
import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands, ui
from discord.ext import commands

logger = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
os.makedirs(DATA_DIR, exist_ok=True)

CATEGORY_NAME  = "Tickets"
LOG_CHANNEL    = "ticket-logs"
SUPPORT_ROLE   = "Support Team"

# ── Colours ───────────────────────────────────────────────────────────────────
BLURPLE   = 0x5865F2
GREEN     = 0x57F287
RED       = 0xED4245
YELLOW    = 0xFEE75C
DARK_GREY = 0x2C2F33


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
    kwargs = {}
    if content  is not None: kwargs["content"]   = content
    if embed    is not None: kwargs["embed"]     = embed
    if view     is not None: kwargs["view"]      = view
    if ephemeral:            kwargs["ephemeral"] = True
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except (discord.NotFound, discord.HTTPException) as exc:
        logger.debug("Ticket response silently dropped (%s): %s", type(exc).__name__, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_tickets() -> dict:
    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_tickets(data: dict) -> None:
    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_open_ticket(data: dict, guild_id: int, user_id: int) -> int | None:
    """Return the existing ticket channel ID for this user, or None."""
    return data.get(str(guild_id), {}).get(str(user_id))


def _register_ticket(data: dict, guild_id: int, user_id: int, channel_id: int) -> None:
    g = str(guild_id)
    if g not in data:
        data[g] = {}
    data[g][str(user_id)] = channel_id
    _save_tickets(data)


def _unregister_ticket(data: dict, guild_id: int, user_id_or_channel: int) -> None:
    """Remove by channel_id (we may not always know the user)."""
    g = str(guild_id)
    if g not in data:
        return
    # Try direct user-key removal first
    if str(user_id_or_channel) in data[g]:
        del data[g][str(user_id_or_channel)]
    else:
        # Find by channel id value
        data[g] = {
            uid: cid for uid, cid in data[g].items()
            if cid != user_id_or_channel
        }
    _save_tickets(data)


def _find_user_by_channel(data: dict, guild_id: int, channel_id: int) -> int | None:
    """Reverse-lookup: channel_id → user_id."""
    for uid, cid in data.get(str(guild_id), {}).items():
        if cid == channel_id:
            return int(uid)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Guild resource helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_or_create_category(guild: discord.Guild) -> discord.CategoryChannel:
    """Return the 'Tickets' category, creating it if it doesn't exist."""
    cat = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if cat is None:
        cat = await guild.create_category(
            CATEGORY_NAME,
            reason="Ticket system: category created automatically",
        )
    return cat


async def _get_or_create_log_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
) -> discord.TextChannel:
    """Return the #ticket-logs channel, creating it under the category if absent."""
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL)
    if ch is None:
        support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE)
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,        # read-only log channel
                read_message_history=True,
            )
        ch = await guild.create_text_channel(
            LOG_CHANNEL,
            category=category,
            overwrites=overwrites,
            topic="Closed ticket transcripts are posted here automatically.",
            reason="Ticket system: log channel created automatically",
        )
    return ch


async def _build_channel_overwrites(
    guild: discord.Guild,
    opener: discord.Member,
) -> dict:
    """
    Build permission overwrites for a new ticket channel:
    • @everyone → deny view
    • Ticket opener → allow view + send
    • Support Team role → allow view + send + manage messages
    """
    allow_opener = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        embed_links=True,
    )
    allow_support = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        manage_messages=True,
        attach_files=True,
        embed_links=True,
    )

    overwrites: dict = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        opener:             allow_opener,
    }
    support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE)
    if support_role:
        overwrites[support_role] = allow_support

    return overwrites


# ─────────────────────────────────────────────────────────────────────────────
# Transcript builder
# ─────────────────────────────────────────────────────────────────────────────

async def _build_transcript(
    channel: discord.TextChannel,
    opener_id: int,
    closed_by: discord.Member,
) -> tuple[io.BytesIO, str]:
    """
    Fetch all messages in *channel* and return (BytesIO file, filename).
    """
    messages = []
    async for msg in channel.history(limit=500, oldest_first=True):
        messages.append(msg)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "═" * 60,
        "  TICKET TRANSCRIPT",
        f"  Channel  : #{channel.name}",
        f"  Opener ID: {opener_id}",
        f"  Closed by: {closed_by.display_name} ({closed_by.id})",
        f"  Closed at: {now_str}",
        f"  Messages : {len(messages)}",
        "═" * 60,
        "",
    ]

    for msg in messages:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        content = msg.content or "(no text content)"
        if msg.attachments:
            content += "  [attachments: " + ", ".join(a.url for a in msg.attachments) + "]"
        lines.append(f"[{ts}] {msg.author.display_name}: {content}")

    text    = "\n".join(lines) + "\n"
    buf     = io.BytesIO(text.encode("utf-8"))
    fname   = f"transcript-{channel.name}.txt"
    return buf, fname


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation view (non-persistent — ephemeral, short-lived)
# ─────────────────────────────────────────────────────────────────────────────

class TicketConfirmCloseView(ui.View):
    """Ephemeral Confirm / Cancel prompt shown when Close Ticket is clicked."""

    def __init__(self, manager: "TicketSystem", channel: discord.TextChannel):
        super().__init__(timeout=60)
        self._mgr     = manager
        self._channel = channel

    async def on_timeout(self):
        # Disable buttons when the prompt expires
        for item in self.children:
            item.disabled = True

    @ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True

        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="🔒  Closing Ticket…",
                    description="Generating transcript and archiving. Channel will be deleted shortly.",
                    colour=RED,
                ),
                view=self,
            )
        except (discord.NotFound, discord.HTTPException):
            return

        await self._mgr._close_ticket(self._channel, interaction.user)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="✖️  Cancelled",
                    description="Ticket closure cancelled. The channel remains open.",
                    colour=DARK_GREY,
                ),
                view=self,
            )
        except (discord.NotFound, discord.HTTPException):
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Persistent: Close Ticket button (lives inside each ticket channel)
# ─────────────────────────────────────────────────────────────────────────────

class TicketCloseView(ui.View):
    def __init__(self, manager: "TicketSystem"):
        super().__init__(timeout=None)
        self._mgr = manager

    @ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:close",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        confirm_embed = discord.Embed(
            title="⚠️  Close this ticket?",
            description=(
                "A full transcript will be saved to **#ticket-logs** "
                "before the channel is deleted.\n\n"
                "This action **cannot** be undone."
            ),
            colour=YELLOW,
        )
        try:
            await interaction.response.send_message(
                embed=confirm_embed,
                view=TicketConfirmCloseView(self._mgr, interaction.channel),
                ephemeral=True,
            )
        except (discord.NotFound, discord.HTTPException) as exc:
            logger.debug("Could not send close-confirm: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Persistent: Open Ticket button (lives in the setup embed)
# ─────────────────────────────────────────────────────────────────────────────

class TicketOpenView(ui.View):
    def __init__(self, manager: "TicketSystem"):
        super().__init__(timeout=None)
        self._mgr = manager

    @ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket:create",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild  = interaction.guild
        opener = interaction.user

        # ── Duplicate check ──────────────────────────────────────────────────
        existing_id = _get_open_ticket(self._mgr._tickets, guild.id, opener.id)
        if existing_id:
            existing_ch = guild.get_channel(existing_id)
            if existing_ch:
                try:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="⚠️  Ticket Already Open",
                            description=f"You already have an open ticket: {existing_ch.mention}\n"
                                        "Please use your existing ticket or close it first.",
                            colour=YELLOW,
                        ),
                        ephemeral=True,
                    )
                except (discord.NotFound, discord.HTTPException):
                    pass
                return
            else:
                # Channel was deleted without going through the close flow — clean up
                _unregister_ticket(self._mgr._tickets, guild.id, existing_id)

        # ── Defer so we have time to create the channel ──────────────────────
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ── Create ticket channel ─────────────────────────────────────────────
        try:
            category   = await _get_or_create_category(guild)
            overwrites = await _build_channel_overwrites(guild, opener)
            # Sanitise username for channel name (Discord allows a-z, 0-9, -)
            safe_name  = "".join(
                c if c.isalnum() or c == "-" else "-"
                for c in opener.display_name.lower()
            ).strip("-") or "user"
            chan_name  = f"ticket-{safe_name}"

            channel = await guild.create_text_channel(
                chan_name,
                category=category,
                overwrites=overwrites,
                topic=f"Support ticket for {opener.display_name} ({opener.id})",
                reason=f"Ticket opened by {opener}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌  Permission Error",
                    description="I don't have **Manage Channels** permission. "
                                "Please ask an admin to fix my permissions.",
                    colour=RED,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            logger.error("Failed to create ticket channel: %s", exc)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌  Error",
                    description="Something went wrong creating your ticket. Please try again.",
                    colour=RED,
                ),
                ephemeral=True,
            )
            return

        # ── Register open ticket ─────────────────────────────────────────────
        _register_ticket(self._mgr._tickets, guild.id, opener.id, channel.id)

        # ── Send welcome message inside the new channel ───────────────────────
        support_role  = discord.utils.get(guild.roles, name=SUPPORT_ROLE)
        role_mention  = support_role.mention if support_role else "**Support Team**"
        welcome_embed = discord.Embed(
            title="🎫  Support Ticket",
            description=(
                f"Welcome, {opener.mention}!\n\n"
                "Please describe your issue in as much detail as possible. "
                f"{role_mention} will be with you shortly.\n\n"
                "When your issue is resolved, click **Close Ticket** below."
            ),
            colour=BLURPLE,
            timestamp=datetime.now(timezone.utc),
        )
        welcome_embed.set_footer(
            text=f"{guild.name}  •  Support System",
            icon_url=guild.icon.url if guild.icon else None,
        )

        await channel.send(
            content=opener.mention,
            embed=welcome_embed,
            view=TicketCloseView(self._mgr),
        )

        # ── Notify opener ─────────────────────────────────────────────────────
        try:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅  Ticket Created",
                    description=f"Your private ticket has been opened: {channel.mention}",
                    colour=GREEN,
                ),
                ephemeral=True,
            )
        except (discord.NotFound, discord.HTTPException):
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class TicketSystem(commands.Cog):
    """Full support ticket lifecycle: open → converse → transcript → close."""

    def __init__(self, bot: commands.Bot):
        self.bot      = bot
        self._tickets = _load_tickets()
        # Register persistent views for restart recovery
        bot.add_view(TicketOpenView(self))
        bot.add_view(TicketCloseView(self))

    # ── /ticket_setup ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="ticket_setup",
        description="[Admin] Post the Support Tickets embed with the Open Ticket button.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫  Support Tickets",
            description=(
                "Click the button below to open a private support ticket.\n\n"
                "A dedicated channel will be created just for you and our "
                "Support Team. Please describe your issue clearly so we can "
                "help you as quickly as possible."
            ),
            colour=BLURPLE,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="📋  What to include",
            value=(
                "• A clear description of your issue\n"
                "• Any relevant screenshots or details\n"
                "• Steps to reproduce (if applicable)"
            ),
            inline=False,
        )
        embed.set_footer(
            text=f"{interaction.guild.name}  •  Support System",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await _safe_respond(
            interaction,
            embed=embed,
            view=TicketOpenView(self),
        )

    # ── Internal: close ticket ────────────────────────────────────────────────

    async def _close_ticket(
        self,
        channel: discord.TextChannel,
        closed_by: discord.Member,
    ) -> None:
        """
        Full close flow:
        1. Build transcript
        2. Find / create #ticket-logs
        3. Post transcript file + summary embed
        4. Unregister ticket
        5. Delete channel
        """
        guild    = channel.guild
        opener_id = _find_user_by_channel(self._tickets, guild.id, channel.id)

        # ── Build transcript ─────────────────────────────────────────────────
        try:
            buf, fname = await _build_transcript(channel, opener_id or 0, closed_by)
        except Exception as exc:
            logger.error("Transcript generation failed: %s", exc)
            buf, fname = io.BytesIO(b"(transcript unavailable)"), f"transcript-{channel.name}.txt"

        # ── Send to log channel ──────────────────────────────────────────────
        try:
            category  = await _get_or_create_category(guild)
            log_ch    = await _get_or_create_log_channel(guild, category)
            log_embed = discord.Embed(
                title="🔒  Ticket Closed",
                colour=RED,
                timestamp=datetime.now(timezone.utc),
            )
            log_embed.add_field(name="📁  Channel",   value=channel.name,            inline=True)
            log_embed.add_field(name="🔒  Closed by", value=closed_by.mention,        inline=True)
            if opener_id:
                log_embed.add_field(name="🎫  Opened by", value=f"<@{opener_id}>",   inline=True)
            log_embed.set_footer(
                text=f"{guild.name}  •  Support System",
                icon_url=guild.icon.url if guild.icon else None,
            )
            buf.seek(0)
            await log_ch.send(
                embed=log_embed,
                file=discord.File(buf, filename=fname),
            )
        except Exception as exc:
            logger.error("Failed to send transcript to log channel: %s", exc)

        # ── Unregister & delete ──────────────────────────────────────────────
        _unregister_ticket(self._tickets, guild.id, channel.id)

        try:
            await channel.delete(reason=f"Ticket closed by {closed_by}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.error("Failed to delete ticket channel %s: %s", channel.name, exc)


# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketSystem(bot))
