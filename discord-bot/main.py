import os
import discord
from discord.ext import commands
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable is not set.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="over the server | !help"
        )
    )
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Use `!help {ctx.command}` for usage.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # silently ignore unknown commands
    else:
        logger.error(f"Unhandled error in {ctx.command}: {error}")
        await ctx.send("❌ An unexpected error occurred.")


async def load_cogs():
    for cog in ["cogs.moderation", "cogs.utility", "cogs.fun", "cogs.help"]:
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
