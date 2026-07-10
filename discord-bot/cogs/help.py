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

        # Dynamically build the command list from loaded cogs
        cog_emojis = {
            "Moderation": "🛡️",
            "Utility": "🔧",
            "Fun": "🎉",
        }

        for cog_name, emoji in cog_emojis.items():
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            cmds = [c for c in cog.get_commands() if not c.hidden]
            if cmds:
                embed.add_field(
                    name=f"{emoji} {cog_name}",
                    value=" ".join(f"`!{c.name}`" for c in cmds),
                    inline=False,
                )

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
