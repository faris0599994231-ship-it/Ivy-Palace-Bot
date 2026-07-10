import os
import discord
from discord import app_commands
from discord.ext import commands
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable is not set.")

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, help_command=None)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global slash command error handler."""
    if isinstance(error, app_commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        msg = f"❌ You need the **{perms}** permission(s) to use this command."
    elif isinstance(error, app_commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        msg = f"❌ I need the **{perms}** permission(s) to do that."
    elif isinstance(error, app_commands.NoPrivateMessage):
        msg = "❌ This command can only be used in a server."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "❌ You don't have permission to use this command."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"❌ This command is on cooldown. Try again in {error.retry_after:.1f}s."
    else:
        logger.error(f"Unhandled app command error: {error}")
        msg = "❌ An unexpected error occurred."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="over the server | /help"
        )
    )
    guild = discord.Object(id=1086980337290501291)
    try:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} slash command(s) to guild {guild.id}")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")


async def load_cogs():
    for cog in ["cogs.moderation", "cogs.utility", "cogs.fun", "cogs.help", "cogs.music"]:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded {cog}")
        except Exception as e:
            logger.error(f"Failed to load {cog}: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
