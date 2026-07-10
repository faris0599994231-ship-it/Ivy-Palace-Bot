import discord
from discord.ext import commands
from datetime import timedelta


class Moderation(commands.Cog):
    """Moderation commands for managing the server."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Kick a member from the server. Usage: !kick @user [reason]"""
        if member == ctx.author:
            return await ctx.send("❌ You cannot kick yourself.")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot kick someone with an equal or higher role.")
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Ban a member from the server. Usage: !ban @user [reason]"""
        if member == ctx.author:
            return await ctx.send("❌ You cannot ban yourself.")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot ban someone with an equal or higher role.")
        await member.ban(reason=reason, delete_message_days=1)
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self, ctx, *, user_id: int):
        """Unban a user by their ID. Usage: !unban <user_id>"""
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user)
            embed = discord.Embed(title="✅ User Unbanned", color=discord.Color.green())
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
        except discord.NotFound:
            await ctx.send("❌ That user is not banned or does not exist.")

    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str = "No reason provided"):
        """Timeout a member. Usage: !timeout @user <minutes> [reason]"""
        if member == ctx.author:
            return await ctx.send("❌ You cannot timeout yourself.")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot timeout someone with an equal or higher role.")
        if minutes < 1 or minutes > 40320:
            return await ctx.send("❌ Timeout duration must be between 1 and 40320 minutes (28 days).")
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(title="⏰ Member Timed Out", color=discord.Color.yellow())
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="untimeout")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(self, ctx, member: discord.Member):
        """Remove a timeout from a member. Usage: !untimeout @user"""
        await member.timeout(None)
        await ctx.send(f"✅ Removed timeout from {member.mention}.")

    @commands.command(name="clear", aliases=["purge"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def clear(self, ctx, amount: int = 10):
        """Delete messages in the channel. Usage: !clear [amount] (default: 10, max: 100)"""
        if amount < 1 or amount > 100:
            return await ctx.send("❌ Amount must be between 1 and 100.")
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
        msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} message(s).")
        await msg.delete(delay=3)

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Warn a member. Usage: !warn @user [reason]"""
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
        except discord.Forbidden:
            pass  # DMs closed


async def setup(bot):
    await bot.add_cog(Moderation(bot))
