import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta


def can_act(interaction: discord.Interaction, target: discord.Member) -> tuple[bool, str]:
    """
    Check whether both the bot and invoker can act on the target member.
    Returns (ok, reason) — if not ok, send reason as an ephemeral error.
    """
    guild = interaction.guild
    invoker = interaction.user

    if target == invoker:
        return False, "❌ You cannot do that to yourself."
    if target == guild.owner:
        return False, "❌ You cannot perform this action on the server owner."
    if isinstance(invoker, discord.Member) and target.top_role >= invoker.top_role and invoker != guild.owner:
        return False, "❌ You cannot act on someone with an equal or higher role than you."
    if target.top_role >= guild.me.top_role:
        return False, "❌ I cannot act on someone whose role is equal to or higher than mine."
    if target == guild.me:
        return False, "❌ I cannot act on myself."
    return True, ""


class Moderation(commands.Cog):
    """Moderation commands for managing the server."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        ok, msg = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(msg, ephemeral=True)
        await interaction.response.defer()
        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            return await interaction.followup.send("❌ I don't have permission to kick that member.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to kick member: {e.text}", ephemeral=True)
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="The member to ban", reason="Reason for the ban")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        ok, msg = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(msg, ephemeral=True)
        await interaction.response.defer()
        try:
            await member.ban(reason=reason, delete_message_days=1)
        except discord.Forbidden:
            return await interaction.followup.send("❌ I don't have permission to ban that member.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to ban member: {e.text}", ephemeral=True)
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="unban", description="Unban a user by their Discord user ID")
    @app_commands.describe(user_id="The Discord user ID to unban")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.guild_only()
    async def unban(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid user ID — must be a number.", ephemeral=True)
        try:
            user = await self.bot.fetch_user(uid)
        except discord.NotFound:
            return await interaction.followup.send("❌ No user found with that ID.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to fetch user: {e.text}", ephemeral=True)
        try:
            await interaction.guild.unban(user)
        except discord.NotFound:
            return await interaction.followup.send("❌ That user is not currently banned.", ephemeral=True)
        except discord.Forbidden:
            return await interaction.followup.send("❌ I don't have permission to unban members.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to unban user: {e.text}", ephemeral=True)
        embed = discord.Embed(title="✅ User Unbanned", color=discord.Color.green())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="timeout", description="Temporarily timeout a member")
    @app_commands.describe(member="The member to timeout", minutes="Duration in minutes (1–40320)", reason="Reason for the timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
        ok, msg = can_act(interaction, member)
        if not ok:
            return await interaction.response.send_message(msg, ephemeral=True)
        if minutes < 1 or minutes > 40320:
            return await interaction.response.send_message("❌ Duration must be between 1 and 40320 minutes (28 days).", ephemeral=True)
        await interaction.response.defer()
        try:
            await member.timeout(timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            return await interaction.followup.send("❌ I don't have permission to timeout that member.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to timeout member: {e.text}", ephemeral=True)
        embed = discord.Embed(title="⏰ Member Timed Out", color=discord.Color.yellow())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="untimeout", description="Remove a timeout from a member")
    @app_commands.describe(member="The member whose timeout to remove")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        if not member.timed_out_until:
            return await interaction.response.send_message(f"❌ {member.mention} is not currently timed out.", ephemeral=True)
        await interaction.response.defer()
        try:
            await member.timeout(None)
        except discord.Forbidden:
            return await interaction.followup.send("❌ I don't have permission to remove that timeout.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to remove timeout: {e.text}", ephemeral=True)
        await interaction.followup.send(f"✅ Removed timeout from {member.mention}.")

    @app_commands.command(name="clear", description="Delete messages in this channel")
    @app_commands.describe(amount="Number of messages to delete (1–100, default 10)")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction, amount: int = 10):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
        except discord.Forbidden:
            return await interaction.followup.send("❌ I don't have permission to delete messages here.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to delete messages: {e.text}", ephemeral=True)
        await interaction.followup.send(f"✅ Deleted {len(deleted)} message(s).", ephemeral=True)

    @app_commands.command(name="warn", description="Warn a member and notify them via DM")
    @app_commands.describe(member="The member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member == interaction.user:
            return await interaction.response.send_message("❌ You cannot warn yourself.", ephemeral=True)
        await interaction.response.defer()
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.yellow())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ You have been warned in {interaction.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.yellow(),
            )
            await member.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
                    pass  # DMs closed or blocked - warning still issued in channel
    @app_commands.command(name="say", description="Sends a message as the bot")
    @app_commands.describe(
        message="The text you want to send",
        image="Select an image from your device"
    )
    async def say(self, interaction: discord.Interaction, message: str, image: discord.Attachment = None):
        # 1. Send the private confirmation message to you first
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
        
        # 2. Send the actual message/image to the channel using the bot's account
        if image:
            file = await image.to_file()
            await interaction.channel.send(content=message, file=file)
        else:
            await interaction.channel.send(content=message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))