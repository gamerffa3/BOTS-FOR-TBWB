# bot.py - Complete Working with Error Logging
import os
import discord
from discord.ext import commands
import requests
import json
import logging
import sys

# ============ LOGGING SETUP (Console mein dikhega) ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('discord')

# ============ TOKENS ============
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GH_TOKEN = os.getenv('GH_TOKEN')

if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not set!")
    exit(1)

if not GH_TOKEN:
    print("❌ GH_TOKEN not set! AI will not work!")
    exit(1)

# ============ BOT INFO ============
BOT_NAME = "CAREFULLY"
CREATOR = "TurboIG"
OWNER = "TurboIG Web"

# ============ BOT ============
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============ AI FUNCTION WITH FULL ERROR LOGGING ============
def ask_ai(prompt):
    """Ask AI using GitHub Models with full error logging"""
    if not GH_TOKEN:
        logger.error("❌ GH_TOKEN is not set!")
        return "❌ GitHub Token not configured!"
    
    try:
        url = "https://models.inference.ai.azure.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "Llama-3.2-3b-instruct",
            "messages": [
                {"role": "system", "content": f"You are {BOT_NAME}, a helpful AI assistant created by {CREATOR}."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        # LOGGING - Console mein dikhega
        logger.info(f"📤 Sending request to GitHub Models API")
        logger.info(f"📤 Prompt: {prompt[:100]}...")
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        # LOGGING - Status code
        logger.info(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ API Response: Success")
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"❌ No choices in response: {result}")
                return "❌ No response from AI"
        else:
            # LOGGING - Error details
            error_text = response.text[:500] if response.text else "No response body"
            logger.error(f"❌ API Error {response.status_code}: {error_text}")
            
            # Try to parse error
            try:
                error_json = response.json()
                logger.error(f"❌ Error JSON: {json.dumps(error_json, indent=2)}")
            except:
                pass
            
            return f"❌ API Error: {response.status_code} - Check console for details"
            
    except requests.Timeout:
        logger.error("⏰ Request timeout!")
        return "⏰ Timeout! Please try again."
    except Exception as e:
        logger.error(f"❌ Exception: {str(e)}")
        return f"❌ Error: {str(e)[:100]}"

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ✅ {BOT_NAME} is ONLINE!                                 ║
║                                                              ║
║     🤖 Bot: {BOT_NAME}                                      
║     👤 Creator: {CREATOR}                                   
║     🌐 Owner: {OWNER}                                       
║     📊 Servers: {len(bot.guilds)}                           
║     🔑 GitHub Token: {"✅ Set" if GH_TOKEN else "❌ Missing"}
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"✅ Bot ready! Logged in as {bot.user}")
    logger.info(f"🔑 GH_TOKEN: {'Set' if GH_TOKEN else 'Missing'}")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!help | @CAREFULLY"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # AI Reply on Tag
    if bot.user.mentioned_in(message):
        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if not prompt:
            await message.reply(f"👋 Hello! I'm {BOT_NAME}, your AI assistant. Ask me anything! 🤖\n- By {CREATOR}")
            return
        
        logger.info(f"📥 Tag from {message.author.name}: {prompt[:100]}...")
        
        async with message.channel.typing():
            response = ask_ai(prompt)
            await message.reply(f"🤖 {response}\n- By {CREATOR}")
        return
    
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!help`", delete_after=5)
    else:
        logger.error(f"❌ Command Error: {error}")
        await ctx.send(f"❌ Error: {str(error)[:100]}", delete_after=5)

# ============ AI COMMANDS ============
@bot.command(name='ai')
async def ai_command(ctx, *, question):
    """Ask AI anything"""
    if len(question) > 1000:
        await ctx.send("❌ Too long! Max 1000 characters.")
        return
    
    logger.info(f"📥 !ai from {ctx.author.name}: {question[:100]}...")
    
    async with ctx.typing():
        response = ask_ai(question)
        await ctx.send(f"🤖 {response}\n- By {CREATOR}")

@bot.command(name='test')
async def test_command(ctx):
    """Test if bot is working"""
    await ctx.send(f"✅ Bot is working! Connected as {bot.user}\n- By {CREATOR}")

@bot.command(name='ping')
async def ping_command(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: **{latency}ms**\n- By {CREATOR}")

@bot.command(name='help')
async def help_command(ctx):
    """Show all commands"""
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME} Commands",
        description=f"Created by **{CREATOR}** • **{OWNER}**",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📌 Tag Bot",
        value=f"`@{BOT_NAME} <question>` - Ask AI by tagging",
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI Commands",
        value="`!ai <question>` - Ask AI\n"
              "`!test` - Test bot\n"
              "`!ping` - Check latency\n"
              "`!help` - Show this menu",
        inline=False
    )
    
    embed.set_footer(text=f"Powered by GitHub Models • {OWNER}")
    await ctx.send(embed=embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        print("🤖 Starting CAREFULLY Bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"❌ Fatal Error: {e}")