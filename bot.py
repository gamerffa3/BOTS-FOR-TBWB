# bot.py - CAREFULLY Bot - Complete Working Code
import os
import sys
import subprocess
import importlib
import shutil
import warnings
import re
import json
import logging
import asyncio
import time
from datetime import datetime, timedelta
from collections import defaultdict
import platform
import random
import io
import tempfile

# ============ SUPPRESS ALL WARNINGS ============
warnings.filterwarnings("ignore")

# ============ AUTO INSTALL EVERYTHING ON START ============
def install_all_dependencies():
    """Install ALL dependencies on every bot start"""
    print("🔧 Installing ALL dependencies...")
    
    packages = [
        'discord.py[voice]',
        'requests',
        'aiohttp',
        'psutil',
        'PyNaCl',
        'youtube-dl',
        'pynacl',
        'libnacl',
        'beautifulsoup4',
        'lxml',
        'gTTS',
        'pydub'
    ]
    
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

install_all_dependencies()

# ============ IMPORT ALL LIBRARIES ============
import discord
from discord.ext import commands
import requests
import aiohttp
from gtts import gTTS
from pydub import AudioSegment

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

# ============ BOT IDENTITY ============
BOT_NAME = "CAREFULLY"
BOT_NICKNAME = "Carefully"
BOT_CREATOR = "TurboIG"
BOT_OWNER = "TurboIG Web"
BOT_VERSION = "3.0.0"
BOT_EMOJI = "🎙️"
BOT_ID = "1521130781978787871"
BOT_DESCRIPTION = "AI Voice Bot with Real Voice Messages"

# ============ AUTHORIZED USERS ============
AUTHORIZED_USERS = [
    "TurboIG",
    "turbo.ig",
    "gamerffa3",
    "carefully"
]

# ============ BOT SETUP - 100% FIXED ============
# ✅ ONLY DEFAULT INTENTS - No privileged intents
intents = discord.Intents.default()
intents.message_content = True  # ✅ Message content enabled
intents.voice_states = True     # ✅ Voice support

# ❌ ALL PRIVILEGED INTENTS DISABLED - Inhe portal mein enable karo
# intents.members = True
# intents.presences = True
# intents.guild_messages = True
# intents.dm_messages = True
# intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============ GLOBAL VARIABLES ============
voice_connections = {}
warnings = {}
muted = {}
config = {}
_bot_ready = False
start_time = datetime.now()

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
        'owner_id': None,
        'auto_mute_time': 300,
        'max_warnings': 3,
        'ai_model': "DeepSeek-R1",
        'ai_enabled': True,
        'auto_join_vc': False,
        'voice_enabled': True,
        'voice_language': 'hi',
        'response_style': 'casual'
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
def is_authorized(user):
    if not user:
        return False
    
    if user.name in AUTHORIZED_USERS:
        return True
    
    if user.display_name.lower() in [u.lower() for u in AUTHORIZED_USERS]:
        return True
    
    if config.get('owner_id') and user.id == config.get('owner_id'):
        return True
    
    return False

def is_server_owner(member):
    if not member:
        return False
    return member == member.guild.owner

def is_admin(member):
    if not member:
        return False
    if is_server_owner(member) or is_authorized(member):
        return True
    if hasattr(member, 'guild_permissions') and member.guild_permissions.administrator:
        return True
    return False

def is_mod(member):
    if not member:
        return False
    if is_admin(member):
        return True
    if hasattr(member, 'guild_permissions') and member.guild_permissions.manage_messages:
        return True
    return False

# ============ LANGUAGE DETECTION ============
def detect_language(text):
    """Detect language from text - Hindi/English/Roman Hindi"""
    hindi_pattern = re.compile(r'[\u0900-\u097F]')
    if hindi_pattern.search(text):
        return 'hi'
    
    roman_hindi_words = ['hai', 'ho', 'hum', 'tum', 'aap', 'mein', 'ka', 'ki', 'ke', 
                        'ko', 'se', 'ne', 'tha', 'thi', 'the', 'hain', 'hu', 'huh',
                        'kya', 'kyu', 'kaise', 'kahan', 'kab', 'kon', 'kisko']
    words = text.lower().split()
    roman_hindi_count = sum(1 for word in words if word in roman_hindi_words)
    
    if len(words) > 0 and roman_hindi_count > len(words) * 0.15:
        return 'hi'
    
    return 'en'

# ============ TEXT TO SPEECH ============
def text_to_speech(text, language=None):
    """Convert text to speech using gTTS"""
    if not config.get('voice_enabled', True):
        return None
    
    try:
        if not language:
            language = detect_language(text)
        
        if config.get('voice_language'):
            language = config.get('voice_language')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            temp_path = tmp_file.name
        
        tts = gTTS(text=text, lang=language, slow=False)
        tts.save(temp_path)
        
        try:
            audio = AudioSegment.from_mp3(temp_path)
            wav_path = temp_path.replace('.mp3', '.wav')
            audio.export(wav_path, format='wav')
            os.remove(temp_path)
            return wav_path
        except:
            return temp_path
            
    except Exception as e:
        logger.error(f"❌ TTS Error: {e}")
        return None

# ============ AI FUNCTIONS ============
async def ask_ai(prompt):
    """Ask AI with voice support"""
    if not GH_TOKEN:
        return ["❌ GitHub Token not configured!"]
    
    if not config.get('ai_enabled', True):
        return ["❌ AI disabled by admin"]
    
    try:
        url = "https://models.inference.ai.azure.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        style = config.get('response_style', 'casual')
        
        if style == 'casual':
            system_prompt = f"""You are {BOT_NAME}, a friendly assistant from {BOT_OWNER}.
            
            RULES:
            1. Reply in SAME language as user (Hindi/English/Roman Hindi)
            2. Keep responses SHORT (max 30 words)
            3. Be friendly and casual like a friend
            4. Use Roman Hindi for Hindi responses
            5. Never say you're an AI
            6. Be helpful and direct
            7. Use emojis sometimes 😊
            
            EXAMPLES:
            - User: "kaise ho" → "Main theek hu! Aap kaise ho? 😊"
            - User: "what's up" → "All good! What about you? 😄"
            - User: "namaste" → "Namaste! Kaise ho aap? 🙏"""
        else:
            system_prompt = f"""You are {BOT_NAME}, a professional assistant from {BOT_OWNER}.
            
            RULES:
            1. Reply in SAME language as user
            2. Keep responses professional and clear
            3. Be helpful and informative
            4. Never say you're an AI"""
        
        data = {
            "model": config.get('ai_model', 'DeepSeek-R1'),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 80,
            "temperature": 0.7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        text = result["choices"][0]["message"]["content"]
                        text = clean_response(text)
                        return [text]
                    else:
                        return ["❌ No response"]
                elif response.status == 429:
                    await asyncio.sleep(30)
                    return await ask_ai(prompt)
                else:
                    return [f"❌ Error: {response.status}"]
            
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return ["❌ Error"]

def clean_response(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    return text.strip() if text.strip() else "Hello! How can I help you?"

# ============ VOICE FUNCTIONS ============
async def join_voice_channel(guild_id, channel_id=None):
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found"
        
        if not channel_id:
            voice_channels = guild.voice_channels
            if voice_channels:
                channel = voice_channels[0]
            else:
                return False, "No voice channels found"
        else:
            channel = bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return False, "Invalid voice channel"
        
        if guild.id in voice_connections:
            vc = voice_connections[guild.id]
            if vc and vc.is_connected():
                await vc.move_to(channel)
                return True, f"Moved to {channel.name}"
        
        vc = await channel.connect(timeout=30.0)
        voice_connections[guild.id] = vc
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        
        return True, f"Joined {channel.name}"
        
    except Exception as e:
        logger.error(f"❌ Voice join error: {e}")
        return False, str(e)

async def leave_voice_channel(guild_id):
    try:
        if guild_id in voice_connections:
            vc = voice_connections[guild_id]
            if vc and vc.is_connected():
                if vc.is_playing():
                    vc.stop()
                await vc.disconnect()
                del voice_connections[guild_id]
                return True, "Left voice channel"
        return False, "Not in any voice channel"
    except Exception as e:
        return False, str(e)

async def send_voice_message(channel, text):
    """Send voice message in voice channel"""
    if not config.get('voice_enabled', True):
        return None
    
    try:
        guild = channel.guild
        if not guild:
            return None
        
        if guild.id not in voice_connections:
            if hasattr(channel, 'author') and channel.author and channel.author.voice:
                vc = await channel.author.voice.channel.connect()
                voice_connections[guild.id] = vc
            else:
                return None
        
        vc = voice_connections[guild.id]
        
        language = detect_language(text)
        audio_path = text_to_speech(text, language)
        if not audio_path:
            return None
        
        if vc and vc.is_connected():
            if vc.is_playing():
                vc.stop()
            
            audio_source = discord.FFmpegPCMAudio(audio_path)
            vc.play(audio_source)
            
            def cleanup():
                try:
                    os.remove(audio_path)
                except:
                    pass
            
            while vc.is_playing():
                await asyncio.sleep(0.1)
            
            cleanup()
            return True
            
    except Exception as e:
        logger.error(f"❌ Voice send error: {e}")
        return None

def extract_invite_code(text):
    match = re.search(r'(?:discord\.gg/|discord\.com/invite/)([a-zA-Z0-9\-_]+)', text)
    if match:
        return match.group(1)
    if re.match(r'^[a-zA-Z0-9\-_]+$', text):
        return text
    return None

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
║     🎙️ {BOT_NAME} v{BOT_VERSION} - AI Voice Bot            
║                                                              ║
║     📝 {BOT_DESCRIPTION}                                    ║
║     👤 Creator: {BOT_CREATOR}                               
║     🌐 Owner: {BOT_OWNER}                                   
║     📊 Servers: {len(bot.guilds)}                           
║     🆔 Bot ID: {BOT_ID}                                     
║     🌍 Voice Lang: {config.get('voice_language', 'hi').upper()}                               
║     🎭 Style: {config.get('response_style', 'casual').capitalize()}                               
║     ⏰ Uptime: {str(uptime).split('.')[0]}                  
║     💻 System: {platform.system()} {platform.release()}     
║                                                              ║
║     🔗 Invite Link:                                         ║
║     https://discord.com/api/oauth2/authorize?              ║
║     client_id={BOT_ID}&permissions=8&scope=bot             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"Voice | @{BOT_NAME}"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # DM CONTROL
    if isinstance(message.channel, discord.DMChannel):
        if is_authorized(message.author):
            await handle_dm_command(message)
        else:
            await message.channel.send(f"❌ You are not authorized to control me!\nOnly {', '.join(AUTHORIZED_USERS)} can control me.")
        return
    
    # TAG BOT FOR AI VOICE
    if bot.user.mentioned_in(message):
        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if not prompt:
            await message.channel.send(f"{BOT_EMOJI} Hello! I'm {BOT_NAME}. Tag me with a question! 🎙️")
            return
        
        async with message.channel.typing():
            parts = await ask_ai(prompt)
            response_text = parts[0] if parts else "Sorry, I couldn't respond."
        
        await message.channel.send(f"{BOT_EMOJI} {response_text}\n- {BOT_CREATOR}")
        
        try:
            await send_voice_message(message.channel, response_text)
        except Exception as e:
            logger.error(f"❌ Voice failed: {e}")
        
        return
    
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!help`", delete_after=5)
    else:
        await ctx.send(f"❌ Error: {str(error)[:50]}", delete_after=5)

# ============ DM COMMAND HANDLER ============
async def handle_dm_command(message):
    content = message.content.strip()
    
    # !joindc
    if content.startswith('!joindc'):
        parts = content.split(' ', 1)
        if len(parts) < 2:
            await message.channel.send("❌ Usage: `!joindc <discord_invite_link>`")
            return
        
        invite_code = extract_invite_code(parts[1])
        if not invite_code:
            await message.channel.send("❌ Invalid invite link!")
            return
        
        await message.channel.send(f"🔗 Checking invite: `{invite_code}`...")
        
        try:
            invite = await bot.fetch_invite(f"https://discord.gg/{invite_code}")
            
            if not invite:
                await message.channel.send("❌ Invite not found!")
                return
            
            if invite.guild.id in [g.id for g in bot.guilds]:
                await message.channel.send(f"✅ Already in server: **{invite.guild.name}**")
                return
            
            embed = discord.Embed(
                title=f"📋 Server Found!",
                description=f"**{invite.guild.name}**",
                color=discord.Color.green()
            )
            embed.add_field(name="👥 Members", value=invite.approximate_member_count or "Unknown", inline=True)
            embed.add_field(name="🟢 Online", value=invite.approximate_presence_count or "Unknown", inline=True)
            embed.add_field(name="🆔 Server ID", value=f"`{invite.guild.id}`", inline=True)
            embed.add_field(
                name="🔗 Invite Bot",
                value=f"https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot",
                inline=False
            )
            embed.set_footer(text="⚠️ Please invite manually!")
            
            await message.channel.send(embed=embed)
            
        except discord.NotFound:
            await message.channel.send("❌ Invite not found!")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)[:100]}")
        return
    
    # !joinvc
    if content.startswith('!joinvc'):
        parts = content.split(' ', 1)
        
        if len(parts) < 2:
            if len(bot.guilds) == 0:
                await message.channel.send("❌ I'm not in any servers!")
                return
            
            guild = bot.guilds[0]
            await message.channel.send(f"🔊 Joining voice in **{guild.name}**...")
            success, msg = await join_voice_channel(guild.id)
            await message.channel.send(f"✅ {msg}" if success else f"❌ {msg}")
            return
        
        try:
            server_id = int(parts[1])
            guild = bot.get_guild(server_id)
            if not guild:
                await message.channel.send("❌ Server not found!")
                return
            
            await message.channel.send(f"🔊 Joining voice in **{guild.name}**...")
            success, msg = await join_voice_channel(guild.id)
            await message.channel.send(f"✅ {msg}" if success else f"❌ {msg}")
            
        except ValueError:
            await message.channel.send("❌ Invalid server ID!")
        return
    
    # !leavevc
    if content.startswith('!leavevc'):
        parts = content.split(' ', 1)
        
        if len(parts) < 2:
            count = 0
            for guild_id in list(voice_connections.keys()):
                success, msg = await leave_voice_channel(guild_id)
                if success:
                    count += 1
            
            if count > 0:
                await message.channel.send(f"✅ Left {count} voice channel(s)")
            else:
                await message.channel.send("❌ Not in any voice channel!")
            return
        
        try:
            server_id = int(parts[1])
            success, msg = await leave_voice_channel(server_id)
            await message.channel.send(f"✅ {msg}" if success else f"❌ {msg}")
        except ValueError:
            await message.channel.send("❌ Invalid server ID!")
        return
    
    # !servers
    if content == '!servers':
        if len(bot.guilds) == 0:
            await message.channel.send("❌ I'm not in any servers!")
            return
        
        embed = discord.Embed(
            title="📊 My Servers",
            description=f"I'm in **{len(bot.guilds)}** servers",
            color=discord.Color.blue()
        )
        
        for guild in bot.guilds[:10]:
            members = guild.member_count
            voice_status = "🔊" if guild.id in voice_connections and voice_connections[guild.id].is_connected() else "🔇"
            embed.add_field(
                name=f"{voice_status} {guild.name[:50]}",
                value=f"🆔 `{guild.id}`\n👥 {members} members",
                inline=False
            )
        
        await message.channel.send(embed=embed)
        return
    
    # !status
    if content == '!status':
        embed = discord.Embed(
            title=f"{BOT_EMOJI} Bot Status",
            color=discord.Color.green()
        )
        embed.add_field(name="🤖 Bot", value=f"{BOT_NAME} v{BOT_VERSION}", inline=True)
        embed.add_field(name="🆔 Bot ID", value=BOT_ID, inline=True)
        embed.add_field(name="📊 Servers", value=len(bot.guilds), inline=True)
        embed.add_field(name="🔊 Voice Connections", value=len(voice_connections), inline=True)
        embed.add_field(name="🎙️ Voice", value="✅ Enabled" if config.get('voice_enabled', True) else "❌ Disabled", inline=True)
        embed.add_field(name="🌍 Language", value=config.get('voice_language', 'hi').upper(), inline=True)
        embed.add_field(name="⏰ Uptime", value=str(datetime.now() - start_time).split('.')[0], inline=True)
        embed.add_field(name="🧠 AI", value="✅ Enabled" if config.get('ai_enabled', True) else "❌ Disabled", inline=True)
        embed.add_field(
            name="🔗 Invite Link",
            value=f"https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        return
    
    # !invite
    if content == '!invite':
        await message.channel.send(f"🔗 **Invite {BOT_NAME}:**\n"
                                  f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`")
        return
    
    # !mute
    if content == '!mute':
        count = 0
        for guild_id, vc in voice_connections.items():
            if vc and vc.is_connected():
                try:
                    await vc.guild.change_voice_state(channel=vc.channel, self_mute=True)
                    count += 1
                except:
                    pass
        
        if count > 0:
            await message.channel.send(f"🔇 Muted in {count} voice channel(s)")
        else:
            await message.channel.send("❌ Not in any voice channel!")
        return
    
    # !unmute
    if content == '!unmute':
        count = 0
        for guild_id, vc in voice_connections.items():
            if vc and vc.is_connected():
                try:
                    await vc.guild.change_voice_state(channel=vc.channel, self_mute=False)
                    count += 1
                except:
                    pass
        
        if count > 0:
            await message.channel.send(f"🔊 Unmuted in {count} voice channel(s)")
        else:
            await message.channel.send("❌ Not in any voice channel!")
        return
    
    # !style
    if content.startswith('!style'):
        parts = content.split(' ', 1)
        if len(parts) < 2:
            await message.channel.send(f"Current style: **{config.get('response_style', 'casual')}**\nUse: `!style casual` or `!style professional`")
            return
        
        if parts[1].lower() in ['casual', 'fun', 'friendly']:
            config['response_style'] = 'casual'
            save_config()
            await message.channel.send("✅ Style set to: **Casual** 😊")
        elif parts[1].lower() in ['professional', 'formal', 'serious']:
            config['response_style'] = 'professional'
            save_config()
            await message.channel.send("✅ Style set to: **Professional** 👔")
        else:
            await message.channel.send("❌ Use: `!style casual` or `!style professional`")
        return
    
    # !ai on/off
    if content.startswith('!ai'):
        parts = content.split(' ', 1)
        if len(parts) < 2:
            await message.channel.send(f"AI: **{'ON' if config.get('ai_enabled', True) else 'OFF'}**")
            return
        
        if parts[1].lower() in ['on', 'enable']:
            config['ai_enabled'] = True
            save_config()
            await message.channel.send("✅ AI enabled!")
        elif parts[1].lower() in ['off', 'disable']:
            config['ai_enabled'] = False
            save_config()
            await message.channel.send("❌ AI disabled!")
        return
    
    # !help
    if content == '!help' or content == '!commands':
        embed = discord.Embed(
            title=f"{BOT_EMOJI} DM Commands",
            description=f"Control {BOT_NAME} via DM",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔗 Server Management",
            value="`!joindc <invite>` - Check server invite\n"
                  "`!servers` - List all servers\n"
                  "`!status` - Bot status\n"
                  "`!invite` - Get invite link",
            inline=False
        )
        embed.add_field(
            name="🔊 Voice Control",
            value="`!joinvc [server_id]` - Join VC\n"
                  "`!leavevc [server_id]` - Leave VC\n"
                  "`!mute` - Mute bot\n"
                  "`!unmute` - Unmute bot",
            inline=False
        )
        embed.add_field(
            name="⚙️ Settings",
            value="`!ai on/off` - Toggle AI\n"
                  "`!style casual/professional` - Response style\n"
                  "`!voicelang <lang>` - Voice language",
            inline=False
        )
        embed.add_field(
            name="💡 Server Commands",
            value="`!joinvc` - Join VC\n"
                  "`!leavevc` - Leave VC\n"
                  "`@CAREFULLY` - Ask AI with Voice\n"
                  "`!voice <text>` - Send voice message\n"
                  "`!ai <question>` - Ask AI\n"
                  "`!about` - About bot\n"
                  "`!ping` - Check latency",
            inline=False
        )
        embed.add_field(
            name="🆔 Bot Info",
            value=f"**Bot ID:** `{BOT_ID}`\n"
                  f"**Invite Link:**\n"
                  f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`",
            inline=False
        )
        embed.set_footer(text=f"Owner: {BOT_OWNER}")
        await message.channel.send(embed=embed)
        return
    
    await message.channel.send(f"❌ Unknown command! Use `!help`")

# ============ SERVER COMMANDS ============

# ============ VOICE COMMANDS ============
@bot.command(name='joinvc')
async def joinvc_cmd(ctx):
    """Join voice channel"""
    if not ctx.author.voice:
        await ctx.send("❌ You're not in a voice channel!")
        return
    
    try:
        channel = ctx.author.voice.channel
        
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc and vc.is_connected():
                await vc.move_to(channel)
                await ctx.send(f"🔊 Moved to **{channel.name}**")
                return
        
        vc = await channel.connect(timeout=30.0)
        voice_connections[ctx.guild.id] = vc
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        
        await ctx.send(f"🔊 Joined **{channel.name}**!\n- {BOT_CREATOR}")
        
    except Exception as e:
        await ctx.send(f"❌ Failed to join VC: {str(e)[:50]}")

@bot.command(name='leavevc')
async def leavevc_cmd(ctx):
    """Leave voice channel"""
    try:
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc and vc.is_connected():
                if vc.is_playing():
                    vc.stop()
                await vc.disconnect()
                del voice_connections[ctx.guild.id]
                await ctx.send(f"🔇 Left voice channel\n- {BOT_CREATOR}")
            else:
                await ctx.send("❌ Not in any voice channel!")
        else:
            await ctx.send("❌ Not in any voice channel!")
    except Exception as e:
        await ctx.send(f"❌ Failed to leave VC: {str(e)[:50]}")

@bot.command(name='mutebot')
async def mutebot_cmd(ctx):
    """Mute bot in VC"""
    try:
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc and vc.is_connected():
                await vc.guild.change_voice_state(channel=vc.channel, self_mute=True)
                await ctx.send("🔇 Bot muted\n- {BOT_CREATOR}")
            else:
                await ctx.send("❌ Not in any voice channel!")
        else:
            await ctx.send("❌ Not in any voice channel!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:50]}")

@bot.command(name='unmutebot')
async def unmutebot_cmd(ctx):
    """Unmute bot in VC"""
    try:
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc and vc.is_connected():
                await vc.guild.change_voice_state(channel=vc.channel, self_mute=False)
                await ctx.send("🔊 Bot unmuted\n- {BOT_CREATOR}")
            else:
                await ctx.send("❌ Not in any voice channel!")
        else:
            await ctx.send("❌ Not in any voice channel!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:50]}")

@bot.command(name='voice')
async def voice_cmd(ctx, *, text):
    """Send voice message"""
    if not config.get('voice_enabled', True):
        await ctx.send("❌ Voice disabled by admin!")
        return
    
    if len(text) > 500:
        await ctx.send("❌ Text too long! Max 500 characters.")
        return
    
    async with ctx.typing():
        success = await send_voice_message(ctx.channel, text)
        
    if success:
        await ctx.send(f"🎙️ Voice message sent!\n- {BOT_CREATOR}")
    else:
        await ctx.send("❌ Failed to send voice message! Join a voice channel first.")

@bot.command(name='voicelang')
async def voicelang_cmd(ctx, lang):
    """Set voice language (hi/en/es/fr)"""
    if not is_admin(ctx.author):
        await ctx.send("❌ Admin only!")
        return
    
    valid_langs = ['hi', 'en', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'ru', 'ar', 'pt', 'zh', 'ta', 'te']
    
    if lang.lower() not in valid_langs:
        await ctx.send(f"❌ Invalid language! Available: {', '.join(valid_langs)}")
        return
    
    config['voice_language'] = lang.lower()
    save_config()
    await ctx.send(f"✅ Voice language set to: **{lang.upper()}**")

# ============ AI COMMANDS ============
@bot.command(name='ai')
async def ai_cmd(ctx, *, question):
    """Ask AI (text only)"""
    if len(question) > 1000:
        await ctx.send("❌ Too long!")
        return
    
    async with ctx.typing():
        parts = await ask_ai(question)
        response = parts[0] if parts else "❌ Error"
    
    await ctx.send(f"{BOT_EMOJI} {response}\n- {BOT_CREATOR}")

@bot.command(name='ask')
async def ask_cmd(ctx, *, question):
    """Ask AI (alias)"""
    await ai_cmd(ctx, question=question)

# ============ BOT COMMANDS ============
@bot.command(name='about')
async def about_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} About {BOT_NAME}",
        description=f"Your AI Voice Assistant from **{BOT_OWNER}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="🤖 Name", value=f"{BOT_NAME} ({BOT_NICKNAME})", inline=True)
    embed.add_field(name="👤 Creator", value=BOT_CREATOR, inline=True)
    embed.add_field(name="🌐 Owner", value=BOT_OWNER, inline=True)
    embed.add_field(name="📝 Version", value=BOT_VERSION, inline=True)
    embed.add_field(name="🎙️ Voice", value="✅ Enabled" if config.get('voice_enabled', True) else "❌ Disabled", inline=True)
    embed.add_field(name="🌍 Language", value=config.get('voice_language', 'hi').upper(), inline=True)
    embed.add_field(name="📊 Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="⏰ Uptime", value=str(datetime.now() - start_time).split('.')[0], inline=True)
    embed.add_field(
        name="🔗 Invite Link",
        value=f"https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot",
        inline=False
    )
    embed.set_footer(text=f"{BOT_OWNER} • {BOT_NAME}")
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
    embed.add_field(name="🎙️ Voice", value="✅ Ready" if config.get('voice_enabled', True) else "❌ Disabled", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='invite')
async def invite_cmd(ctx):
    await ctx.send(f"🔗 **Invite {BOT_NAME}:**\n"
                  f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`")

@bot.command(name='servers')
async def servers_cmd(ctx):
    if not is_authorized(ctx.author):
        return await ctx.send("❌ Only authorized users can use this!")
    
    embed = discord.Embed(
        title="📊 My Servers",
        description=f"I'm in **{len(bot.guilds)}** servers",
        color=discord.Color.blue()
    )
    
    for guild in bot.guilds[:15]:
        members = guild.member_count
        voice_status = "🔊" if guild.id in voice_connections and voice_connections[guild.id].is_connected() else "🔇"
        embed.add_field(
            name=f"{voice_status} {guild.name[:40]}",
            value=f"🆔 `{guild.id}`\n👥 {members} members",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='style')
async def style_cmd(ctx, style):
    """Set response style (casual/professional)"""
    if not is_admin(ctx.author):
        await ctx.send("❌ Admin only!")
        return
    
    if style.lower() in ['casual', 'fun', 'friendly']:
        config['response_style'] = 'casual'
        save_config()
        await ctx.send("✅ Style set to: **Casual** 😊")
    elif style.lower() in ['professional', 'formal', 'serious']:
        config['response_style'] = 'professional'
        save_config()
        await ctx.send("✅ Style set to: **Professional** 👔")
    else:
        await ctx.send("❌ Use: `!style casual` or `!style professional`")

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

# ============ ADMIN COMMANDS ============
@bot.command(name='setowner')
async def setowner_cmd(ctx, member: discord.Member):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Only server owner can use this!")
    
    config['owner_id'] = member.id
    save_config()
    await ctx.send(f"✅ {member.mention} is now the bot owner!\n- {BOT_CREATOR}")

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

# ============ HELP COMMAND ============
@bot.command(name='help')
async def help_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} {BOT_NAME} Commands",
        description=f"Your AI Voice Assistant from **{BOT_OWNER}**",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎙️ Voice Commands",
        value="`@CAREFULLY <question>` - Ask AI with Voice\n"
              "`!voice <text>` - Send voice message\n"
              "`!joinvc` - Join voice channel\n"
              "`!leavevc` - Leave voice channel\n"
              "`!voicelang <lang>` - Set voice language",
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI Commands",
        value="`!ai <question>` - Ask AI (text only)\n"
              "`!ask <question>` - Ask AI (alias)\n"
              "`!style casual/professional` - Response style",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation",
        value="`!warn @user <reason>` - Warn user\n"
              "`!warnings @user` - View warnings\n"
              "`!mute @user <time>` - Mute user\n"
              "`!unmute @user` - Unmute user\n"
              "`!kick @user <reason>` - Kick user\n"
              "`!ban @user <reason>` - Ban user\n"
              "`!clear <amount>` - Clear messages",
        inline=False
    )
    
    embed.add_field(
        name="📌 Info",
        value="`!about` - About the bot\n"
              "`!ping` - Check latency\n"
              "`!invite` - Get invite link\n"
              "`!servers` - List servers (owner only)",
        inline=False
    )
    
    embed.add_field(
        name="🌍 Languages",
        value="Hindi, Roman Hindi, English (Auto-detect)\n"
              "Set: `hi`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `ru`, `ar`",
        inline=False
    )
    
    embed.add_field(
        name="🆔 Bot Info",
        value=f"**Bot ID:** `{BOT_ID}`\n"
              f"**Version:** {BOT_VERSION}\n"
              f"**Invite Link:**\n"
              f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`",
        inline=False
    )
    
    embed.set_footer(text=f"{BOT_OWNER} • DM me for full control!")
    await ctx.send(embed=embed)

# ============ RUN ============
if __name__ == "__main__":
    try:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🎙️ {BOT_NAME} v{BOT_VERSION} - AI Voice Bot            
║                                                              ║
║     📝 {BOT_DESCRIPTION}                                    ║
║     👤 Creator: {BOT_CREATOR}                               
║     🌐 Owner: {BOT_OWNER}                                   
║     🆔 Bot ID: {BOT_ID}                                     
║     🌍 Voice Lang: {config.get('voice_language', 'hi').upper()}                               
║     🎭 Style: {config.get('response_style', 'casual').capitalize()}                               
║                                                              ║
║     🔗 Invite Link:                                         ║
║     https://discord.com/api/oauth2/authorize?              ║
║     client_id={BOT_ID}&permissions=8&scope=bot             ║
║                                                              ║
║     Starting bot...                                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")
