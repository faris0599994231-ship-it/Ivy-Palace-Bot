import discord
from discord import app_commands
from discord.ext import commands
import random


class Fun(commands.Cog):
    """Fun and entertainment commands."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll dice (e.g. 2d20)")
    @app_commands.describe(dice="Dice notation in NdN format, e.g. 2d6 (default: 1d6)")
    async def roll(self, interaction: discord.Interaction, dice: str = "1d6"):
        try:
            parts = dice.lower().split("d")
            if len(parts) != 2:
                raise ValueError
            count, sides = int(parts[0]), int(parts[1])
            if count < 1 or count > 50 or sides < 2 or sides > 1000:
                raise ValueError
        except (ValueError, IndexError):
            return await interaction.response.send_message(
                "❌ Invalid format. Use `NdN` (e.g. `2d6`, `1d20`, `4d8`).", ephemeral=True
            )

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ", ".join(str(r) for r in rolls) if count <= 20 else f"{count} rolls"

        embed = discord.Embed(title="🎲 Dice Roll", color=discord.Color.purple())
        embed.add_field(name="Dice", value=f"{count}d{sides}", inline=True)
        embed.add_field(name="Rolls", value=rolls_str, inline=True)
        embed.add_field(name="Total", value=f"**{total}**", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"It landed on **{result}**!",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="eightball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question for the magic 8-ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = [
            ("It is certain.", True), ("It is decidedly so.", True),
            ("Without a doubt.", True), ("Yes, definitely.", True),
            ("You may rely on it.", True), ("As I see it, yes.", True),
            ("Most likely.", True), ("Outlook good.", True),
            ("Yes.", True), ("Signs point to yes.", True),
            ("Reply hazy, try again.", None), ("Ask again later.", None),
            ("Better not tell you now.", None), ("Cannot predict now.", None),
            ("Concentrate and ask again.", None),
            ("Don't count on it.", False), ("My reply is no.", False),
            ("My sources say no.", False), ("Outlook not so good.", False),
            ("Very doubtful.", False),
        ]
        response, positive = random.choice(responses)
        color = (
            discord.Color.green() if positive is True
            else discord.Color.red() if positive is False
            else discord.Color.grey()
        )
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=color)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=response, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="choose", description="Let the bot pick between options separated by |")
    @app_commands.describe(options="Options separated by | (e.g. cats | dogs | fish)")
    async def choose(self, interaction: discord.Interaction, options: str):
        choices = [o.strip() for o in options.split("|") if o.strip()]
        if len(choices) < 2:
            return await interaction.response.send_message(
                "❌ Please provide at least 2 options separated by `|`. Example: `cats | dogs`",
                ephemeral=True,
            )
        chosen = random.choice(choices)
        embed = discord.Embed(title="🤔 I Choose...", color=discord.Color.blurple())
        embed.add_field(name="Options", value=" | ".join(choices), inline=False)
        embed.add_field(name="My Pick", value=f"**{chosen}**", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll", description="Create a yes/no poll with reactions")
    @app_commands.describe(question="The poll question")
    @app_commands.guild_only()
    async def poll(self, interaction: discord.Interaction, question: str):
        embed = discord.Embed(
            title="📊 Poll",
            description=question,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Poll by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        try:
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
        except (discord.Forbidden, discord.HTTPException):
            pass  # reactions failed — embed is still visible

    @app_commands.command(name="rps", description="Play rock, paper, scissors against the bot")
    @app_commands.describe(choice="Your move")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Rock 🪨", value="rock"),
        app_commands.Choice(name="Paper 📄", value="paper"),
        app_commands.Choice(name="Scissors ✂️", value="scissors"),
    ])
    async def rps(self, interaction: discord.Interaction, choice: str):
        options = ["rock", "paper", "scissors"]
        bot_choice = random.choice(options)
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if choice == bot_choice:
            result, color = "It's a tie!", discord.Color.grey()
        elif (
            (choice == "rock" and bot_choice == "scissors")
            or (choice == "scissors" and bot_choice == "paper")
            or (choice == "paper" and bot_choice == "rock")
        ):
            result, color = "You win! 🎉", discord.Color.green()
        else:
            result, color = "I win! 😎", discord.Color.red()

        embed = discord.Embed(title="✊ Rock, Paper, Scissors", color=color)
        embed.add_field(name="Your Choice", value=f"{emojis[choice]} {choice.capitalize()}", inline=True)
        embed.add_field(name="My Choice", value=f"{emojis[bot_choice]} {bot_choice.capitalize()}", inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
