import discord
from discord.ext import commands
from datetime import datetime, timezone


class Utility(commands.Cog):
    """Utility and information commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        """Check the bot's latency. Usage: !ping"""
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 100 else discord.Color.yellow() if latency < 200 else discord.Color.red()
        embed = discord.Embed(title="🏓 Pong!", description=f"Latency: **{latency}ms**", color=color)
        await ctx.send(embed=embed)

    @commands.command(name="serverinfo", aliases=["si"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """Show information about the server. Usage: !serverinfo"""
        guild = ctx.guild
        created = guild.created_at.strftime("%B %d, %Y")
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)

        embed = discord.Embed(title=f"📊 {guild.name}", color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=f"{guild.member_count} total / ~{online} online", inline=True)
        embed.add_field(name="Created", value=created, inline=True)
        embed.add_field(name="Channels", value=f"{len(guild.text_channels)} text / {len(guild.voice_channels)} voice", inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        embed.set_footer(text=f"Server ID: {guild.id}")
        await ctx.send(embed=embed)

    @commands.command(name="userinfo", aliases=["ui", "whois"])
    @commands.guild_only()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Show information about a user. Usage: !userinfo [@user]"""
        member = member or ctx.author
        joined = member.joined_at.strftime("%B %d, %Y") if member.joined_at else "Unknown"
        created = member.created_at.strftime("%B %d, %Y")

        roles = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        roles_str = ", ".join(roles[:10]) if roles else "None"
        if len(roles) > 10:
            roles_str += f" (+{len(roles) - 10} more)"

        embed = discord.Embed(
            title=f"👤 {member}",
            color=member.color if member.color != discord.Color.default() else discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.add_field(name="Account Created", value=created, inline=True)
        embed.add_field(name="Joined Server", value=joined, inline=True)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(name="Bot?", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Roles", value=roles_str, inline=False)
        embed.set_footer(text=f"User ID: {member.id}")
        await ctx.send(embed=embed)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar(self, ctx, member: discord.Member = None):
        """Get a user's avatar. Usage: !avatar [@user]"""
        member = member or ctx.author
        embed = discord.Embed(title=f"🖼️ {member.display_name}'s Avatar", color=discord.Color.blurple())
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")
        await ctx.send(embed=embed)

    @commands.command(name="roleinfo", aliases=["ri"])
    @commands.guild_only()
    async def roleinfo(self, ctx, *, role: discord.Role):
        """Get info about a role. Usage: !roleinfo <role name or @role>"""
        created = role.created_at.strftime("%B %d, %Y")
        members_with_role = len(role.members)
        color_hex = str(role.color) if role.color != discord.Color.default() else "Default"

        embed = discord.Embed(title=f"🏷️ Role: {role.name}", color=role.color)
        embed.add_field(name="ID", value=str(role.id), inline=True)
        embed.add_field(name="Color", value=color_hex, inline=True)
        embed.add_field(name="Members", value=str(members_with_role), inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Created", value=created, inline=True)
        embed.set_footer(text=f"Position: {role.position}")
        await ctx.send(embed=embed)

    @commands.command(name="botinfo")
    async def botinfo(self, ctx):
        """Show information about this bot. Usage: !botinfo"""
        embed = discord.Embed(
            title=f"🤖 {self.bot.user.name}",
            description="A general-purpose Discord bot with moderation, utility, and fun commands.",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Prefix", value="`!`", inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(sum(g.member_count for g in self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Library", value="discord.py", inline=True)
        embed.set_footer(text=f"Bot ID: {self.bot.user.id}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
