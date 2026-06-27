# bot.py - Secure Discord Bot
import discord
from discord.ext import commands
import os

# 🔴 Token GitHub Secrets se le rahe hain! (Code mein nahi!)
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("❌ Error: DISCORD_TOKEN not found in environment!")
    exit(1)

# Intents enable karo
intents = discord.Intents.default()
intents.message_content = True

# Bot banayein
bot = commands.Bot(command_prefix='!', intents=intents)

# Bot online
@bot.event
async def on_ready():
    print(f'✅ Bot Online! {bot.user}')
    await bot.change_presence(activity=discord.Game(name="!ping"))

# Command: !ping
@bot.command()
async def ping(ctx):
    await ctx.send('🏓 Pong!')

# Command: !hello
@bot.command()
async def hello(ctx):
    await ctx.send(f'👋 Hello {ctx.author.mention}!')

# Manual message response
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if 'hello' in message.content.lower():
        await message.channel.send('Hello there!')
    
    await bot.process_commands(message)

# Run
bot.run(TOKEN)
