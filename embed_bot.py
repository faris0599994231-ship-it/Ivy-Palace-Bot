import discord
from discord.ext import commands
from discord import app_commands


class EmbedBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="embed",
        description="إنشاء رسالة Embed"
    )
    @app_commands.describe(
        title="عنوان الـ Embed",
        description="محتوى الـ Embed",
        color="لون الـ Embed مثل #5865F2"
    )
    async def embed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color: str = "#5865F2"
    ):
        color = color.replace("#", "").strip()

        try:
            if len(color) != 6:
                raise ValueError

            embed_color = discord.Color(int(color, 16))

        except ValueError:
            await interaction.response.send_message(
                "❌ اللون غير صحيح. مثال: `#5865F2`",
                ephemeral=True
            )
            return

        embed_message = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )

        embed_message.set_footer(
            text=f"بواسطة {interaction.user.name}"
        )

        await interaction.response.send_message(
            embed=embed_message
        )


async def setup(bot):
    await bot.add_cog(EmbedBot(bot))