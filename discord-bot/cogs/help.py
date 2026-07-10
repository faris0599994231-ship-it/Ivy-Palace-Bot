import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    """Help command."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available slash commands")
    @app_commands.describe(command="A specific command to get details for (optional)")
    async def help_command(self, interaction: discord.Interaction, command: str = None):
        if command:
            # Find the command in the tree
            cmd = self.bot.tree.get_command(command)
            if not cmd:
                return await interaction.response.send_message(
                    f"❌ Command `/{command}` not found. Use `/help` to see all commands.",
                    ephemeral=True,
                )
            embed = discord.Embed(
                title=f"📖 /{cmd.name}",
                description=cmd.description or "No description available.",
                color=discord.Color.blurple(),
            )
            if hasattr(cmd, "_params"):
                params = [f"`{name}` — {p.description}" for name, p in cmd._params.items()]
                if params:
                    embed.add_field(name="Parameters", value="\n".join(params), inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="📖 Slash Commands",
            description="Use `/help <command>` for details on a specific command.",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        cog_emojis = {
            "Moderation": ("🛡️", ["kick", "ban", "unban", "timeout", "untimeout", "clear", "warn"]),
            "Utility":    ("🔧", ["ping", "serverinfo", "userinfo", "avatar", "roleinfo", "botinfo"]),
            "Fun":        ("🎉", ["roll", "flip", "eightball", "choose", "poll", "rps", "say"]),
        }

        for cog_name, (emoji, cmd_names) in cog_emojis.items():
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            loaded = {c.name for c in cog.get_app_commands()}
            visible = [name for name in cmd_names if name in loaded]
            if visible:
                embed.add_field(
                    name=f"{emoji} {cog_name}",
                    value=" ".join(f"`/{name}`" for name in visible),
                    inline=False,
                )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
