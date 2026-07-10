import discord
from discord.ext import commands


class Help(commands.Cog):
    """Custom help command."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["h", "commands"])
    async def help_command(self, ctx, *, command_name: str = None):
        """Show all commands or info about a specific command. Usage: !help [command]"""
        if command_name:
            cmd = self.bot.get_command(command_name)
            if not cmd:
                return await ctx.send(f"❌ Command `{command_name}` not found. Use `!help` to see all commands.")
            embed = discord.Embed(
                title=f"📖 Command: !{cmd.name}",
                description=cmd.help or "No description available.",
                color=discord.Color.blurple(),
            )
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(f"`!{a}`" for a in cmd.aliases), inline=False)
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📖 Bot Commands",
            description="Use `!help <command>` for more info on a specific command.\nPrefix: `!`",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        categories = {
            "🛡️ Moderation": ["kick", "ban", "unban", "timeout", "untimeout", "clear", "warn"],
            "🔧 Utility": ["ping", "serverinfo", "userinfo", "avatar", "roleinfo", "botinfo"],
            "🎉 Fun": ["roll", "flip", "8ball", "choose", "poll", "rps", "say"],
        }

        for category, cmds in categories.items():
            cmd_list = []
            for name in cmds:
                cmd = self.bot.get_command(name)
                if cmd:
                    cmd_list.append(f"`!{cmd.name}`")
            if cmd_list:
                embed.add_field(name=category, value=" ".join(cmd_list), inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
