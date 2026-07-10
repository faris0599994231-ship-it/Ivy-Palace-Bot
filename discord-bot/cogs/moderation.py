import discord
from discord.ext import commands
from datetime import timedelta


def can_act(ctx: commands.Context, target: discord.Member) -> tuple[bool, str]:
    """
    Check whether the bot and invoker can both act on the target.
    Returns (ok, reason) — if not ok, send reason as the error message.
    """
    guild = ctx.guild
    if target == ctx.author:
        return False, "❌ You cannot do that to yourself."
    if target == guild.owner:
        return False, "❌ You cannot perform this action on the server owner."
    if target.top_role >= ctx.author.top_role and ctx.author != guild.owner:
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

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Kick a member from the server. Usage: !kick @user [reason]"""
        ok, msg = can_act(ctx, member)
        if not ok:
            return await ctx.send(msg)
        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to kick that member.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to kick member: {e.text}")
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Ban a member from the server. Usage: !ban @user [reason]"""
        ok, msg = can_act(ctx, member)
        if not ok:
            return await ctx.send(msg)
        try:
            await member.ban(reason=reason, delete_message_days=1)
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to ban that member.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to ban member: {e.text}")
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self, ctx, *, user_id: int):
        """Unban a user by their ID. Usage: !unban <user_id>"""
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return await ctx.send("❌ No user found with that ID.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to fetch user: {e.text}")
        try:
            await ctx.guild.unban(user)
        except discord.NotFound:
            return await ctx.send("❌ That user is not currently banned.")
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to unban members.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to unban user: {e.text}")
        embed = discord.Embed(title="✅ User Unbanned", color=discord.Color.green())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str = "No reason provided"):
        """Timeout a member. Usage: !timeout @user <minutes> [reason]"""
        ok, msg = can_act(ctx, member)
        if not ok:
            return await ctx.send(msg)
        if minutes < 1 or minutes > 40320:
            return await ctx.send("❌ Duration must be between 1 and 40320 minutes (28 days).")
        try:
            await member.timeout(timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to timeout that member.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to timeout member: {e.text}")
        embed = discord.Embed(title="⏰ Member Timed Out", color=discord.Color.yellow())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="untimeout")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(self, ctx, member: discord.Member):
        """Remove a timeout from a member. Usage: !untimeout @user"""
        if not member.timed_out_until:
            return await ctx.send(f"❌ {member.mention} is not currently timed out.")
        try:
            await member.timeout(None)
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to remove that timeout.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to remove timeout: {e.text}")
        await ctx.send(f"✅ Removed timeout from {member.mention}.")

    @commands.command(name="clear", aliases=["purge"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def clear(self, ctx, amount: int = 10):
        """Delete messages in the channel. Usage: !clear [amount] (default: 10, max: 100)"""
        if amount < 1 or amount > 100:
            return await ctx.send("❌ Amount must be between 1 and 100.")
        try:
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to delete messages here.")
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Failed to delete messages: {e.text}")
        msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} message(s).")
        await msg.delete(delay=3)

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Warn a member. Usage: !warn @user [reason]"""
        if member == ctx.author:
            return await ctx.send("❌ You cannot warn yourself.")
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.yellow())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ You have been warned in {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.yellow(),
            )
            await member.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass  # DMs closed or blocked — not an error, warning was still issued


async def setup(bot):
    await bot.add_cog(Moderation(bot))
