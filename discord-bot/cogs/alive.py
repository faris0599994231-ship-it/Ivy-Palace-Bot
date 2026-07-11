import logging

import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

ALIVE_CHANNEL_ID = 1524262458448150578


class Alive(commands.Cog):
    """Periodically posts a heartbeat message to keep the bot active."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.send_alive.start()

    def cog_unload(self):
        self.send_alive.cancel()

    @tasks.loop(minutes=5)
    async def send_alive(self):
        channel = self.bot.get_channel(ALIVE_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ALIVE_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden) as e:
                logger.warning(f"Cannot reach alive channel {ALIVE_CHANNEL_ID}: {e}")
                return
        try:
            await channel.send("I am alive!")
        except discord.Forbidden:
            logger.warning(f"Missing permission to send messages in channel {ALIVE_CHANNEL_ID}.")
        except discord.HTTPException as e:
            logger.warning(f"Failed to send alive message: {e}")

    @send_alive.before_loop
    async def before_send_alive(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Alive(bot))
