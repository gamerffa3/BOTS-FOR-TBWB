# bot.py - Complete Discord Bot with Auto Install Everything on Every Start
import os
import sys
import subprocess
import importlib
import shutil
import warnings

# ============ SUPPRESS ALL WARNINGS ============
warnings.filterwarnings("ignore")

# ============ AUTO INSTALL EVERYTHING ON START ============
def install_all_dependencies():
    """Install ALL dependencies on every bot start"""
    print("🔧 Installing ALL dependencies...")
    
    # List of ALL required packages
    packages = [
        'discord.py[voice]',
        'requests',
        'aiohttp',
        'psutil',
        'PyNaCl',
        'youtube-dl',
        'pynacl',
        'libnacl'
    ]
    
    # Install each package
    for package in packages:
        print(f"📦 Installing {package}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", package, "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✅ {package} installed!")
        except:
            print(f"⚠️ Could not install {package}")
    
    # Install FFmpeg (system level)
    install_ffmpeg()
    
    print("✅ All dependencies installed!")

def install_ffmpeg():
    """Install FFmpeg system-wide"""
    if shutil.which("ffmpeg") is not None:
        print("✅ FFmpeg already installed!")
        return True
    
    print("📦 Installing FFmpeg...")
    try:
        if sys.platform.startswith('linux'):
            # For GitHub Actions / Ubuntu
            subprocess.check_call(["sudo", "apt-get", "update", "-qq"], 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
            subprocess.check_call(["sudo", "apt-get", "install", "-y", "ffmpeg"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            print("✅ FFmpeg installed!")
            return True
        elif sys.platform == 'darwin':
            subprocess.check_call(["brew", "install", "ffmpeg"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            print("✅ FFmpeg installed!")
            return True
        else:
            print("⚠️ Please install FFmpeg manually")
            return False
    except:
        print("⚠️ Could not install FFmpeg")
        return False

# ============ RUN INSTALLATION ============
install_all_dependencies()

# ============ NOW IMPORT ALL LIBRARIES ============
import discord
from discord.ext import commands
import requests
import json
import logging
import asyncio
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict
import platform
import psutil
import aiohttp

# ============ LOGGING ============
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

# ============ BOT IDENTITY ============
BOT_NAME = "CAREFULLY"
BOT_NICKNAME = "Carefully"
BOT_AGE = "2.0"
BOT_CREATOR = "TurboIG"
BOT_OWNER = "TurboIG Web"
BOT_VERSION = "2.0.0"
BOT_GENDER = "Male"
BOT_PERSONALITY = "Friendly, Helpful, Professional, Funny, Smart"
BOT_LANGUAGES = "English, Hindi, Urdu, Roman Hindi, Spanish"
BOT_PURPOSE = "To help, moderate, and entertain the TurboIG Web community"
BOT_SPECIALTY = "AI Conversations, Code Generation, Moderation, Voice Commands"
BOT_FAVORITE = "Helping people and learning new things"
BOT_MOTTO = "Always here to help, 24/7!"
BOT_BIRTHDAY = "June 28, 2026"
BOT_TEAM = "TurboIG Web Development Team"
BOT_EMOJI = "🤖"

# ============ SYSTEM INFO ============
SYSTEM_INFO = {
    "OS": platform.system(),
    "OS Version": platform.release(),
    "Python Version": platform.python_version(),
    "Processor": platform.processor() or "Unknown",
    "Machine": platform.machine(),
    "Hostname": platform.node()
}

# ============ DEFAULT MODEL ============
DEFAULT_MODEL = "DeepSeek-R1"

# ============ RATE LIMIT ============
last_request_time = 0
MIN_INTERVAL = 2

# ============ GLOBAL VARIABLES ============
voice_connections = {}
warnings = {}
muted = {}
config = {}
_bot_ready = False
start_time = datetime.now()

# ============ BOT SETUP ============
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============ CONFIG ============
def load_config():
    global config
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            return
        except:
            pass
    
    config = {
        'log_channel': None,
        'mute_channel': None,
        'owner_id': None,
        'auto_mute_time': 300,
        'max_warnings': 3,
        'spam_threshold': 5,
        'spam_timeframe': 5,
        'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 
                     'benchod', 'bhak', 'bsdk', 'fuck', 'shit', 'asshole'],
        'mod_roles': [],
        'admin_roles': [],
        'ai_model': DEFAULT_MODEL,
        'ai_enabled': True
    }
    save_config()

def save_config():
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
    except:
        pass

load_config()

# ============ PERMISSION CHECKS ============
def is_server_owner(member):
    if not member:
        return False
    return member == member.guild.owner

def is_owner(member):
    if not member:
        return False
    return member.id == config.get('owner_id')

def is_admin(member):
    if not member:
        return False
    if is_server_owner(member) or is_owner(member):
        return True
    if hasattr(member, 'guild_permissions') and member.guild_permissions.administrator:
        return True
    if hasattr(member, 'roles'):
        for role in member.roles:
            if role.id in config.get('admin_roles', []):
                return True
    return False

def is_mod(member):
    if not member:
        return False
    if is_admin(member) or is_server_owner(member) or is_owner(member):
        return True
    if hasattr(member, 'guild_permissions') and member.guild_permissions.manage_messages:
        return True
    if hasattr(member, 'roles'):
        for role in member.roles:
            if role.id in config.get('mod_roles', []):
                return True
    return False

# ============ HELPERS ============
def clean_response(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    return text.strip() if text.strip() else "Hello! How can I help you?"

def split_into_parts(text, max_len=1800):
    if len(text) <= max_len:
        return [text]
    
    parts = []
    current = ""
    
    for para in text.split('\n\n'):
        if len(current) + len(para) + 2 <= max_len:
            current += para + "\n\n"
        else:
            if current:
                parts.append(current.strip())
            current = para + "\n\n"
    
    if current:
        parts.append(current.strip())
    
    final_parts = []
    for part in parts:
        if len(part) > max_len:
            sentences = re.split(r'(?<=[.!?])\s+', part)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= max_len:
                    current += sent + " "
                else:
                    if current:
                        final_parts.append(current.strip())
                    current = sent + " "
            if current:
                final_parts.append(current.strip())
        else:
            final_parts.append(part)
    
    return final_parts if final_parts else [text[:max_len]]

# ============ ASYNC AI ============
async def ask_ai(prompt):
    global last_request_time
    
    if not GH_TOKEN:
        return ["❌ GitHub Token not configured!"]
    
    if not config.get('ai_enabled', True):
        return ["❌ AI disabled by admin"]
    
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < MIN_INTERVAL:
        wait_time = MIN_INTERVAL - time_since_last
        await asyncio.sleep(wait_time)
    
    try:
        url = "https://models.inference.ai.azure.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        system_prompt = f"""You are {BOT_NAME} (also known as {BOT_NICKNAME}).
        
        YOUR IDENTITY:
        - Name: {BOT_NAME}
        - Nickname: {BOT_NICKNAME}
        - Created by: {BOT_CREATOR}
        - Owner: {BOT_OWNER}
        - Version: {BOT_VERSION}
        - Gender: {BOT_GENDER}
        - Personality: {BOT_PERSONALITY}
        - Languages: {BOT_LANGUAGES}
        - Purpose: {BOT_PURPOSE}
        - Specialty: {BOT_SPECIALTY}
        - Motto: {BOT_MOTTO}
        - Birthday: {BOT_BIRTHDAY}
        - Team: {BOT_TEAM}
        
        YOUR RULES:
        1. Always introduce yourself as {BOT_NAME} from {BOT_OWNER}
        2. Respond in the SAME language as the user
        3. Keep responses SHORT (max 100 words)
        4. Be {BOT_PERSONALITY}
        5. Never say you're an AI or language model
        6. You are a real person/assistant
        7. Be helpful, friendly, and professional
        8. If user asks about you, share your identity details
        9. No thinking tags in response
        10. Direct, clear answers only
        
        Keep responses VERY SHORT and TO THE POINT. Maximum 100 words."""
        
        data = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        last_request_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        text = result["choices"][0]["message"]["content"]
                        text = clean_response(text)
                        parts = split_into_parts(text)
                        return parts
                    else:
                        return ["❌ No response"]
                elif response.status == 429:
                    await asyncio.sleep(30)
                    return await ask_ai(prompt)
                else:
                    return [f"❌ Error: {response.status}"]
            
    except asyncio.TimeoutError:
        return ["⏰ Timeout! Try again."]
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return ["❌ Error"]

# ============ SEND PART BY PART ============
async def send_part_by_part(channel, parts):
    total = len(parts)
    
    for i, part in enumerate(parts):
        if not part or part.strip() == "":
            continue
        
        if total > 1:
            header = f"📄 Part {i+1}/{total}\n"
        else:
            header = ""
        
        content = f"{BOT_EMOJI} {header}{part}\n- {BOT_CREATOR} | {BOT_OWNER}"
        
        if len(content) > 2000:
            for j in range(0, len(content), 1900):
                await channel.send(content[j:j+1900])
        else:
            await channel.send(content)

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    global _bot_ready
    if _bot_ready:
        return
    _bot_ready = True
    
    uptime = datetime.now() - start_time
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ✅ {BOT_NAME} is ONLINE!                                 ║
║                                                              ║
║     🤖 Name: {BOT_NAME} ({BOT_NICKNAME})                    
║     👤 Creator: {BOT_CREATOR}                               
║     🌐 Owner: {BOT_OWNER}                                   
║     📊 Servers: {len(bot.guilds)}                           
║     📝 Version: {BOT_VERSION}                               
║     🎂 Birthday: {BOT_BIRTHDAY}                             
║     🧠 Model: {DEFAULT_MODEL}                               
║     ⏰ Uptime: {str(uptime).split('.')[0]}                  
║     💻 System: {SYSTEM_INFO['OS']} {SYSTEM_INFO['OS Version']}
║     🐍 Python: {SYSTEM_INFO['Python Version']}              
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{BOT_OWNER} | !help"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if bot.user.mentioned_in(message):
        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if not prompt:
            await message.channel.send(f"{BOT_EMOJI} Hello! I'm {BOT_NAME}, your AI assistant from {BOT_OWNER}. Ask me anything! 🤖\n- {BOT_CREATOR}")
            return
        
        async with message.channel.typing():
            parts = await ask_ai(prompt)
            await send_part_by_part(message.channel, parts)
        return
    
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!help`", delete_after=5)
    else:
        await ctx.send(f"❌ Error", delete_after=5)

# ============ VOICE COMMANDS ============
@bot.command(name='join')
async def join_cmd(ctx, channel_id: int = None):
    """Join a voice channel"""
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    try:
        if channel_id:
            channel = bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return await ctx.send("❌ Invalid voice channel!")
        else:
            if not ctx.author.voice:
                return await ctx.send("❌ You're not in a VC! Please join a voice channel first.")
            channel = ctx.author.voice.channel
        
        if ctx.guild.id in voice_connections:
            if voice_connections[ctx.guild.id].is_connected():
                await voice_connections[ctx.guild.id].disconnect()
                del voice_connections[ctx.guild.id]
        
        vc = await channel.connect(timeout=30.0)
        voice_connections[ctx.guild.id] = vc
        
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        
        await ctx.send(f"🔊 Successfully joined **{channel.name}**! (Muted)\n- {BOT_CREATOR} | {BOT_OWNER}")
        
        asyncio.create_task(idle_disconnect(ctx.guild.id))
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to join that voice channel!")
    except Exception as e:
        logger.error(f"❌ Voice join error: {e}")
        await ctx.send(f"❌ Failed to join VC: {str(e)[:50]}")

@bot.command(name='leave')
async def leave_cmd(ctx):
    """Leave the voice channel"""
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    try:
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc and vc.is_connected():
                await vc.disconnect()
                del voice_connections[ctx.guild.id]
                await ctx.send(f"🔇 Left the voice channel\n- {BOT_CREATOR} | {BOT_OWNER}")
            else:
                await ctx.send("❌ Not in any voice channel!")
        else:
            await ctx.send("❌ Not in any voice channel!")
    except Exception as e:
        logger.error(f"❌ Voice leave error: {e}")
        await ctx.send("❌ Failed to leave VC!")

async def idle_disconnect(guild_id, timeout=300):
    await asyncio.sleep(timeout)
    if guild_id in voice_connections:
        vc = voice_connections[guild_id]
        if vc and vc.is_connected():
            await vc.disconnect()
            del voice_connections[guild_id]

# ============ COMMANDS ============
@bot.command(name='about')
async def about_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} About {BOT_NAME}",
        description=f"Your friendly AI assistant from **{BOT_OWNER}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="🤖 Name", value=f"{BOT_NAME} ({BOT_NICKNAME})", inline=True)
    embed.add_field(name="👤 Creator", value=BOT_CREATOR, inline=True)
    embed.add_field(name="🌐 Owner", value=BOT_OWNER, inline=True)
    embed.add_field(name="📝 Version", value=BOT_VERSION, inline=True)
    embed.add_field(name="🎂 Birthday", value=BOT_BIRTHDAY, inline=True)
    embed.add_field(name="🧠 Model", value=DEFAULT_MODEL, inline=True)
    embed.add_field(name="💬 Languages", value=BOT_LANGUAGES, inline=False)
    embed.add_field(name="🎭 Personality", value=BOT_PERSONALITY, inline=False)
    embed.add_field(name="💡 Motto", value=f"*{BOT_MOTTO}*", inline=False)
    embed.add_field(name="📊 Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="⏰ Uptime", value=str(datetime.now() - start_time).split('.')[0], inline=True)
    embed.set_footer(text=f"{BOT_OWNER} • {BOT_NAME}")
    await ctx.send(embed=embed)

@bot.command(name='whoami')
async def whoami_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} I am {BOT_NAME}!",
        description=f"Your AI assistant from **{BOT_OWNER}**",
        color=discord.Color.green()
    )
    embed.add_field(name="👤 Name", value=f"{BOT_NAME} ({BOT_NICKNAME})", inline=True)
    embed.add_field(name="🎂 Age", value=f"{BOT_AGE} (Born {BOT_BIRTHDAY})", inline=True)
    embed.add_field(name="💬 Languages", value=BOT_LANGUAGES, inline=True)
    embed.add_field(name="🎭 Personality", value=BOT_PERSONALITY, inline=False)
    embed.add_field(name="💡 Motto", value=f"*{BOT_MOTTO}*", inline=False)
    embed.add_field(name="👨‍💻 Created by", value=f"{BOT_CREATOR} • {BOT_OWNER}", inline=False)
    embed.set_footer(text=f"Version {BOT_VERSION}")
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping_cmd(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency}ms**",
        color=discord.Color.green()
    )
    embed.add_field(name="🤖 Bot", value=f"{BOT_NAME} v{BOT_VERSION}", inline=True)
    embed.add_field(name="👤 Creator", value=BOT_CREATOR, inline=True)
    embed.set_footer(text=BOT_OWNER)
    await ctx.send(embed=embed)

@bot.command(name='uptime')
async def uptime_cmd(ctx):
    uptime = datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    embed = discord.Embed(
        title="⏰ Bot Uptime",
        description=f"{BOT_NAME} has been online for:",
        color=discord.Color.blue()
    )
    embed.add_field(name="📅 Days", value=days, inline=True)
    embed.add_field(name="⌛ Hours", value=hours, inline=True)
    embed.add_field(name="⏱️ Minutes", value=minutes, inline=True)
    embed.add_field(name="🔄 Total", value=f"{days}d {hours}h {minutes}m {seconds}s", inline=False)
    embed.add_field(name="🤖 Bot", value=f"{BOT_NAME} v{BOT_VERSION}", inline=True)
    embed.add_field(name="🌐 Owner", value=BOT_OWNER, inline=True)
    embed.set_footer(text=f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    await ctx.send(embed=embed)

@bot.command(name='ai')
async def ai_cmd(ctx, *, question):
    if len(question) > 1000:
        await ctx.send("❌ Too long!")
        return
    
    async with ctx.typing():
        parts = await ask_ai(question)
        await send_part_by_part(ctx.channel, parts)

@bot.command(name='ask')
async def ask_cmd(ctx, *, question):
    await ai_cmd(ctx, question=question)

@bot.command(name='system')
async def system_cmd(ctx):
    if not is_admin(ctx.author):
        return await ctx.send("❌ Admin only!")
    
    embed = discord.Embed(
        title="💻 System Information",
        color=discord.Color.blue()
    )
    embed.add_field(name="🖥️ OS", value=f"{SYSTEM_INFO['OS']} {SYSTEM_INFO['OS Version']}", inline=True)
    embed.add_field(name="🐍 Python", value=SYSTEM_INFO['Python Version'], inline=True)
    embed.add_field(name="💾 Processor", value=SYSTEM_INFO['Processor'][:30], inline=True)
    embed.add_field(name="📡 Hostname", value=SYSTEM_INFO['Hostname'], inline=True)
    embed.add_field(name="🤖 Bot", value=f"{BOT_NAME} v{BOT_VERSION}", inline=True)
    embed.add_field(name="🧠 Model", value=DEFAULT_MODEL, inline=True)
    embed.set_footer(text=f"{BOT_OWNER}")
    await ctx.send(embed=embed)

# ============ HELP COMMAND ============
@bot.command(name='help')
async def help_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} {BOT_NAME} Commands",
        description=f"Your AI Assistant from **{BOT_OWNER}**\n*{BOT_MOTTO}*",
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
              "`!ask <question>` - Ask AI (alias)\n"
              "`!about` - About the bot\n"
              "`!whoami` - Who is the bot?\n"
              "`!ping` - Check latency\n"
              "`!uptime` - Bot uptime",
        inline=False
    )
    
    if is_mod(ctx.author):
        embed.add_field(
            name="🛡️ Moderation",
            value="`!warn @user <reason>` - Warn user\n"
                  "`!warnings @user` - View warnings\n"
                  "`!mute @user <time> <reason>` - Mute user\n"
                  "`!unmute @user` - Unmute user\n"
                  "`!kick @user <reason>` - Kick user\n"
                  "`!ban @user <reason>` - Ban user\n"
                  "`!clear <amount>` - Clear messages",
            inline=False
        )
        
        embed.add_field(
            name="🔊 Voice Commands",
            value="`!join` - Join your VC\n"
                  "`!join <channel_id>` - Join specific VC\n"
                  "`!leave` - Leave VC\n"
                  "`!mutebot` - Mute bot in VC\n"
                  "`!unmutebot` - Unmute bot in VC",
            inline=False
        )
    
    if is_admin(ctx.author) or is_server_owner(ctx.author):
        embed.add_field(
            name="⚙️ Admin",
            value="`!setowner @user` - Set bot owner\n"
                  "`!system` - System info\n"
                  "`!serverlock` - Lock server\n"
                  "`!serverunlock` - Unlock server",
            inline=False
        )
    
    embed.add_field(
        name="💡 Info",
        value=f"**Creator:** {BOT_CREATOR}\n**Owner:** {BOT_OWNER}\n**Version:** {BOT_VERSION}\n**Model:** {DEFAULT_MODEL}",
        inline=False
    )
    
    embed.set_footer(text=f"{BOT_MOTTO} • {BOT_OWNER}")
    await ctx.send(embed=embed)

@bot.command(name='setowner')
async def setowner_cmd(ctx, member: discord.Member):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Only server owner can use this!")
    
    config['owner_id'] = member.id
    save_config()
    await ctx.send(f"✅ {member.mention} is now the bot owner!\n- {BOT_CREATOR}")

# ============ MOD COMMANDS ============
@bot.command(name='warn')
async def warn_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    if member.id not in warnings:
        warnings[member.id] = []
    
    warnings[member.id].append({
        'reason': reason,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'mod': ctx.author.name
    })
    
    embed = discord.Embed(title="⚠️ Warned", description=f"{member.mention}", color=discord.Color.orange())
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Total", value=len(warnings[member.id]))
    embed.add_field(name="Moderator", value=ctx.author.mention)
    embed.set_footer(text=f"{BOT_OWNER}")
    await ctx.send(embed=embed)
    
    if len(warnings[member.id]) >= config.get('max_warnings', 3):
        await mute_user(member, config.get('auto_mute_time', 300), "Max warnings")

@bot.command(name='warnings')
async def warnings_cmd(ctx, member: discord.Member):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    if member.id not in warnings or not warnings[member.id]:
        return await ctx.send(f"✅ {member.mention} has no warnings!")
    
    embed = discord.Embed(title=f"⚠️ Warnings for {member.name}", color=discord.Color.orange())
    embed.add_field(name="Total", value=len(warnings[member.id]), inline=False)
    
    for i, warn in enumerate(warnings[member.id][-5:], 1):
        embed.add_field(
            name=f"#{i}",
            value=f"**Reason:** {warn['reason']}\n**Time:** {warn['time']}\n**By:** {warn['mod']}",
            inline=False
        )
    embed.set_footer(text=f"{BOT_OWNER}")
    await ctx.send(embed=embed)

async def mute_user(member, time, reason):
    try:
        if is_admin(member) or is_server_owner(member):
            return False
        
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await member.guild.create_role(name="Muted")
            for channel in member.guild.channels:
                try:
                    await channel.set_permissions(mute_role, 
                        send_messages=False, speak=False, connect=False)
                except:
                    continue
        
        muted[member.id] = {
            'end': datetime.now() + timedelta(seconds=time),
            'reason': reason
        }
        await member.add_roles(mute_role, reason=f"Muted: {reason}")
        
        async def unmute():
            await asyncio.sleep(time)
            if member.id in muted:
                try:
                    await member.remove_roles(mute_role)
                    del muted[member.id]
                except:
                    pass
        
        bot.loop.create_task(unmute())
        return True
    except:
        return False

@bot.command(name='mute')
async def mute_cmd(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    if is_admin(member) or is_server_owner(member):
        return await ctx.send("❌ Can't mute this user!")
    
    if time < 1 or time > 86400:
        return await ctx.send("❌ Time must be 1-86400 seconds!")
    
    if await mute_user(member, time, reason):
        await ctx.send(f"🔇 {member.mention} muted for {time}s\n- {BOT_CREATOR} | {BOT_OWNER}")
    else:
        await ctx.send("❌ Failed to mute!")

@bot.command(name='unmute')
async def unmute_cmd(ctx, member: discord.Member):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if mute_role:
            await member.remove_roles(mute_role)
        del muted[member.id]
        await ctx.send(f"🔊 {member.mention} unmuted!\n- {BOT_CREATOR} | {BOT_OWNER}")
    else:
        await ctx.send(f"❌ {member.mention} is not muted!")

@bot.command(name='kick')
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} kicked!\nReason: {reason}\n- {BOT_CREATOR} | {BOT_OWNER}")
    except:
        await ctx.send("❌ Failed to kick!")

@bot.command(name='ban')
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} banned!\nReason: {reason}\n- {BOT_CREATOR} | {BOT_OWNER}")
    except:
        await ctx.send("❌ Failed to ban!")

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Amount must be 1-100!")
    
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages!\n- {BOT_CREATOR}")
        await asyncio.sleep(2)
        await msg.delete()
    except:
        await ctx.send("❌ Failed to clear messages!")

@bot.command(name='serverlock')
async def serverlock_cmd(ctx):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Only server owner can use this!")
    
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        except:
            continue
    
    await ctx.send(f"🔒 Server Locked!\n- {BOT_CREATOR} | {BOT_OWNER}")

@bot.command(name='serverunlock')
async def serverunlock_cmd(ctx):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Only server owner can use this!")
    
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        except:
            continue
    
    await ctx.send(f"🔓 Server Unlocked!\n- {BOT_CREATOR} | {BOT_OWNER}")

# ============ RUN ============
if __name__ == "__main__":
    try:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🤖 {BOT_NAME} v{BOT_VERSION}                             
║                                                              ║
║     👤 Creator: {BOT_CREATOR}                               
║     🌐 Owner: {BOT_OWNER}                                   
║     📝 Version: {BOT_VERSION}                               
║     🧠 Model: {DEFAULT_MODEL}                               
║                                                              ║
║     Starting bot...                                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")
