import discord
from discord.ext import commands
import random


class Fun(commands.Cog):
    """Fun and entertainment commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="roll", aliases=["dice"])
    async def roll(self, ctx, dice: str = "1d6"):
        """Roll dice. Usage: !roll [NdN] (e.g. !roll 2d20)"""
        try:
            parts = dice.lower().split("d")
            if len(parts) != 2:
                raise ValueError
            count, sides = int(parts[0]), int(parts[1])
            if count < 1 or count > 50 or sides < 2 or sides > 1000:
                raise ValueError
        except (ValueError, IndexError):
            return await ctx.send("❌ Invalid dice format. Use `NdN` (e.g. `2d6`, `1d20`).")

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ", ".join(str(r) for r in rolls) if count <= 20 else f"{count} rolls"

        embed = discord.Embed(title="🎲 Dice Roll", color=discord.Color.purple())
        embed.add_field(name="Dice", value=f"{count}d{sides}", inline=True)
        embed.add_field(name="Rolls", value=rolls_str, inline=True)
        embed.add_field(name="Total", value=f"**{total}**", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="flip", aliases=["coinflip", "coin"])
    async def flip(self, ctx):
        """Flip a coin. Usage: !flip"""
        result = random.choice(["Heads 🪙", "Tails 🪙"])
        embed = discord.Embed(title="🪙 Coin Flip", description=f"It landed on **{result}**!", color=discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.command(name="8ball", aliases=["eightball"])
    async def eightball(self, ctx, *, question: str):
        """Ask the magic 8-ball a question. Usage: !8ball <question>"""
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
        color = discord.Color.green() if positive else discord.Color.red() if positive is False else discord.Color.grey()

        embed = discord.Embed(title="🎱 Magic 8-Ball", color=color)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=response, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="choose", aliases=["pick"])
    async def choose(self, ctx, *, options: str):
        """Let the bot choose between options. Usage: !choose option1 | option2 | ..."""
        choices = [o.strip() for o in options.split("|") if o.strip()]
        if len(choices) < 2:
            return await ctx.send("❌ Please provide at least 2 options separated by `|`. Example: `!choose cats | dogs`")
        chosen = random.choice(choices)
        embed = discord.Embed(title="🤔 I Choose...", color=discord.Color.blurple())
        embed.add_field(name="Options", value=" | ".join(choices), inline=False)
        embed.add_field(name="My Pick", value=f"**{chosen}**", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="poll")
    @commands.guild_only()
    async def poll(self, ctx, *, question: str):
        """Create a simple yes/no poll. Usage: !poll <question>"""
        embed = discord.Embed(
            title="📊 Poll",
            description=question,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Poll by {ctx.author.display_name}")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await ctx.message.delete()

    @commands.command(name="rps")
    async def rps(self, ctx, choice: str):
        """Play rock, paper, scissors. Usage: !rps <rock/paper/scissors>"""
        options = ["rock", "paper", "scissors"]
        choice = choice.lower()
        if choice not in options:
            return await ctx.send("❌ Choose `rock`, `paper`, or `scissors`.")
        bot_choice = random.choice(options)
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        if choice == bot_choice:
            result, color = "It's a tie!", discord.Color.grey()
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "scissors" and bot_choice == "paper") or \
             (choice == "paper" and bot_choice == "rock"):
            result, color = "You win! 🎉", discord.Color.green()
        else:
            result, color = "I win! 😎", discord.Color.red()

        embed = discord.Embed(title="✊ Rock, Paper, Scissors", color=color)
        embed.add_field(name="Your Choice", value=f"{emojis[choice]} {choice.capitalize()}", inline=True)
        embed.add_field(name="My Choice", value=f"{emojis[bot_choice]} {bot_choice.capitalize()}", inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="say")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, message: str):
        """Make the bot say something. Usage: !say <message>"""
        await ctx.message.delete()
        await ctx.send(message)


async def setup(bot):
    await bot.add_cog(Fun(bot))
