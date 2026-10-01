import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    print(f"✅ البوت يعمل: {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"✅ تم تسجيل {len(synced)} أمر")
    except Exception as e:
        print(f"❌ خطأ في تسجيل الأوامر: {e}")


@bot.event
async def on_message(message):
    if message.guild is not None and not message.author.bot:

        MY_ID = 1090319545476071424

        try:
            owner = await bot.fetch_user(MY_ID)

            dm_alert = (
                f"📩 رسالة جديدة\n"
                f"من: {message.author} ({message.author.id})\n"
                f"الرسالة: {message.content}"
            )

            await owner.send(dm_alert)

        except Exception as e:
            print(e)

    await bot.process_commands(message)


async def load_extensions():
    await bot.load_extension("embed_bot")


async def main():
    await load_extensions()
    await bot.start(TOKEN)


import asyncio

if __name__ == "__main__":
    asyncio.run(main())