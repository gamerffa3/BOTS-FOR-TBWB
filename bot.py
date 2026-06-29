# bot.py - Complete Discord Bot with Full Control (Fully Working)
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
        'lxml'
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
BOT_VERSION = "2.0.0"
BOT_EMOJI = "🤖"
BOT_ID = "1202290872994254989"

# ============ AUTHORIZED USERS (DM Control) ============
AUTHORIZED_USERS = [
    "TurboIG",
    "turbo.ig",
    "gamerffa3",
    "carefully",
    "1202290872994254989"  # Bot ID itself
]

# ============ BOT SETUP ============
intents = discord.Intents.all()
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
        'auto_join_vc': False
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
    """Check if user is authorized to control bot"""
    if not user:
        return False
    
    # Check by username
    if user.name in AUTHORIZED_USERS:
        return True
    
    # Check by display name
    if user.display_name.lower() in [u.lower() for u in AUTHORIZED_USERS]:
        return True
    
    # Check by ID
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

# ============ AI FUNCTIONS ============
async def ask_ai(prompt):
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
        
        system_prompt = f"""You are {BOT_NAME} (also known as {BOT_NICKNAME}).
        
        YOUR IDENTITY:
        - Name: {BOT_NAME}
        - Nickname: {BOT_NICKNAME}
        - Created by: {BOT_CREATOR}
        - Owner: {BOT_OWNER}
        - Version: {BOT_VERSION}
        - Personality: Friendly, Helpful, Professional, Funny, Smart
        - Languages: English, Hindi, Urdu, Roman Hindi, Spanish
        - Motto: Always here to help, 24/7!
        
        YOUR RULES:
        1. Always introduce yourself as {BOT_NAME} from {BOT_OWNER}
        2. Respond in the SAME language as the user
        3. Keep responses SHORT (max 100 words)
        4. Be friendly, helpful, and professional
        5. Never say you're an AI or language model
        6. You are a real person/assistant
        7. Direct, clear answers only
        8. If user asks about you, share your identity"""
        
        data = {
            "model": "DeepSeek-R1",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        text = result["choices"][0]["message"]["content"]
                        text = clean_response(text)
                        return split_into_parts(text)
                    else:
                        return ["❌ No response"]
                elif response.status == 429:
                    await asyncio.sleep(30)
                    return await ask_ai(prompt)
                else:
                    return [f"❌ Error: {response.status}"]
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return ["❌ Error"]

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
    
    return parts if parts else [text[:max_len]]

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

# ============ VOICE FUNCTIONS ============
async def join_voice_channel(guild_id, channel_id=None):
    """Join a voice channel in a server"""
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            return False, "Guild not found"
        
        # If no channel specified, try to find a voice channel
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
        
        # Check if already connected
        if guild.id in voice_connections:
            vc = voice_connections[guild.id]
            if vc and vc.is_connected():
                await vc.move_to(channel)
                return True, f"Moved to {channel.name}"
        
        # Connect to voice channel
        vc = await channel.connect(timeout=30.0)
        voice_connections[guild.id] = vc
        
        # Mute bot initially
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        
        return True, f"Joined {channel.name}"
        
    except Exception as e:
        logger.error(f"❌ Voice join error: {e}")
        return False, str(e)

async def leave_voice_channel(guild_id):
    """Leave voice channel"""
    try:
        if guild_id in voice_connections:
            vc = voice_connections[guild_id]
            if vc and vc.is_connected():
                await vc.disconnect()
                del voice_connections[guild_id]
                return True, "Left voice channel"
        return False, "Not in any voice channel"
    except Exception as e:
        return False, str(e)

def extract_invite_code(text):
    """Extract discord invite code from text"""
    # Pattern for discord.gg links
    match = re.search(r'(?:discord\.gg/|discord\.com/invite/)([a-zA-Z0-9\-_]+)', text)
    if match:
        return match.group(1)
    
    # Check if the text itself is an invite code
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
║     ✅ {BOT_NAME} is ONLINE!                                 ║
║                                                              ║
║     🤖 Name: {BOT_NAME} ({BOT_NICKNAME})                    
║     👤 Creator: {BOT_CREATOR}                               
║     🌐 Owner: {BOT_OWNER}                                   
║     📊 Servers: {len(bot.guilds)}                           
║     📝 Version: {BOT_VERSION}                               
║     🆔 Bot ID: {BOT_ID}                                     
║     ⏰ Uptime: {str(uptime).split('.')[0]}                  
║     💻 System: {platform.system()} {platform.release()}     
║     🐍 Python: {platform.python_version()}                  
║                                                              ║
║     📱 Invite Link:                                         ║
║     https://discord.com/api/oauth2/authorize?              ║
║     client_id={BOT_ID}&permissions=8&scope=bot             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{BOT_OWNER} | DM for control"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # ============ DM CONTROL ============
    if isinstance(message.channel, discord.DMChannel):
        if is_authorized(message.author):
            await handle_dm_command(message)
        else:
            await message.channel.send(f"❌ You are not authorized to control me!\nOnly {', '.join(AUTHORIZED_USERS)} can control me.")
        return
    
    # ============ SERVER CHAT CONTROL ============
    # Tag the bot for AI
    if bot.user.mentioned_in(message):
        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if not prompt:
            await message.channel.send(f"{BOT_EMOJI} Hello! I'm {BOT_NAME}, your AI assistant from {BOT_OWNER}. Ask me anything! 🤖\n- {BOT_CREATOR}")
            return
        
        async with message.channel.typing():
            parts = await ask_ai(prompt)
            await send_part_by_part(message.channel, parts)
        return
    
    # ============ AUTO JOIN VC ON COMMAND ============
    if message.content.startswith('!joinvc'):
        if is_admin(message.author):
            await handle_join_vc(message)
        return
    
    await bot.process_commands(message)

# ============ DM COMMAND HANDLER ============
async def handle_dm_command(message):
    """Handle commands from DM"""
    content = message.content.strip()
    
    # ============ !joindc <server_invite> ============
    if content.startswith('!joindc'):
        parts = content.split(' ', 1)
        if len(parts) < 2:
            await message.channel.send("❌ Usage: `!joindc <discord_invite_link>`\nExample: `!joindc https://discord.gg/abc123`")
            return
        
        invite_code = extract_invite_code(parts[1])
        if not invite_code:
            await message.channel.send("❌ Invalid invite link! Use: `https://discord.gg/code` or `discord.gg/code`")
            return
        
        await message.channel.send(f"🔗 Attempting to join server with invite: `{invite_code}`...")
        
        try:
            invite = await bot.fetch_invite(f"https://discord.gg/{invite_code}")
            
            if not invite:
                await message.channel.send("❌ Invite not found! Check the code.")
                return
            
            # Check if already in server
            if invite.guild.id in [g.id for g in bot.guilds]:
                await message.channel.send(f"✅ Already in server: **{invite.guild.name}**")
                return
            
            # Try to join
            try:
                await bot.accept_invite(invite.code)
                await message.channel.send(f"✅ Successfully joined server: **{invite.guild.name}**!")
                await message.channel.send(f"📊 Server ID: `{invite.guild.id}`")
                
                # Auto join voice if enabled
                if config.get('auto_join_vc', False):
                    await message.channel.send("🔊 Auto-joining voice channel...")
                    success, msg = await join_voice_channel(invite.guild.id)
                    await message.channel.send(f"✅ {msg}" if success else f"❌ {msg}")
                    
            except discord.HTTPException as e:
                if "403" in str(e):
                    await message.channel.send(f"❌ Cannot join **{invite.guild.name}**!\n"
                                              f"Please invite me manually using this link:\n"
                                              f"`https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot`\n\n"
                                              f"Then try again.")
                else:
                    await message.channel.send(f"❌ Error: {str(e)[:100]}")
                    
        except discord.NotFound:
            await message.channel.send("❌ Invite not found! Check the code.\n"
                                      f"📝 Invite: `{invite_code}`")
        except discord.Forbidden:
            await message.channel.send("❌ I don't have permission to join this server!\n"
                                      f"Please invite me manually using this link:\n"
                                      f"`https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot`")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)[:100]}")
        return
    
    # ============ !joinvc [server_id] ============
    if content.startswith('!joinvc'):
        parts = content.split(' ', 1)
        
        # If no server ID specified, use the first available server
        if len(parts) < 2:
            if len(bot.guilds) == 0:
                await message.channel.send("❌ I'm not in any servers! Use `!joindc` first.")
                return
            
            # Join voice in first server
            guild = bot.guilds[0]
            await message.channel.send(f"🔊 Joining voice in **{guild.name}**...")
            success, msg = await join_voice_channel(guild.id)
            await message.channel.send(f"✅ {msg}" if success else f"❌ {msg}")
            return
        
        # Join voice in specific server
        try:
            server_id = int(parts[1])
            guild = bot.get_guild(server_id)
            if not guild:
                await message.channel.send("❌ Server not found! Use `!servers` to list all servers.")
                return
            
            await message.channel.send(f"🔊 Joining voice in **{guild.name}**...")
            success, msg = await join_voice_channel(guild.id)
            await message.channel.send(f"✅ {msg}" if success else f"❌ {msg}")
            
        except ValueError:
            await message.channel.send("❌ Invalid server ID! Use: `!joinvc <server_id>`")
        return
    
    # ============ !leavevc [server_id] ============
    if content.startswith('!leavevc'):
        parts = content.split(' ', 1)
        
        if len(parts) < 2:
            # Leave all voice channels
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
    
    # ============ !servers ============
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
        
        if len(bot.guilds) > 10:
            embed.set_footer(text=f"And {len(bot.guilds) - 10} more servers...")
        
        await message.channel.send(embed=embed)
        return
    
    # ============ !status ============
    if content == '!status':
        embed = discord.Embed(
            title=f"{BOT_EMOJI} Bot Status",
            color=discord.Color.green()
        )
        embed.add_field(name="🤖 Bot", value=f"{BOT_NAME} v{BOT_VERSION}", inline=True)
        embed.add_field(name="🆔 Bot ID", value=BOT_ID, inline=True)
        embed.add_field(name="📊 Servers", value=len(bot.guilds), inline=True)
        embed.add_field(name="🔊 Voice Connections", value=len(voice_connections), inline=True)
        embed.add_field(name="⏰ Uptime", value=str(datetime.now() - start_time).split('.')[0], inline=True)
        embed.add_field(name="🧠 AI", value="✅ Enabled" if config.get('ai_enabled', True) else "❌ Disabled", inline=True)
        embed.add_field(name="👤 Creator", value=BOT_CREATOR, inline=True)
        embed.add_field(name="🌐 Owner", value=BOT_OWNER, inline=True)
        embed.add_field(
            name="🔗 Invite Link",
            value=f"https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        return
    
    # ============ !invite ============
    if content == '!invite':
        await message.channel.send(f"🔗 **Invite {BOT_NAME} to your server:**\n"
                                  f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`")
        return
    
    # ============ !help ============
    if content == '!help' or content == '!commands':
        embed = discord.Embed(
            title=f"{BOT_EMOJI} DM Commands",
            description="Control the bot via DM",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔗 Server Management",
            value="`!joindc <invite_link>` - Join a server\n"
                  "`!servers` - List all servers\n"
                  "`!status` - Bot status\n"
                  "`!invite` - Get bot invite link",
            inline=False
        )
        embed.add_field(
            name="🔊 Voice Control",
            value="`!joinvc [server_id]` - Join voice channel\n"
                  "`!leavevc [server_id]` - Leave voice channel\n"
                  "`!mute` - Mute bot in VC\n"
                  "`!unmute` - Unmute bot in VC",
            inline=False
        )
        embed.add_field(
            name="⚙️ Settings",
            value="`!ai on/off` - Enable/disable AI\n"
                  "`!autojoin on/off` - Auto join VC on server join",
            inline=False
        )
        embed.add_field(
            name="💡 Server Chat Commands",
            value="`!joinvc` - Join VC (in server)\n"
                  "`!leavevc` - Leave VC (in server)\n"
                  "`@CAREFULLY <question>` - Ask AI\n"
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
    
    # ============ !mute ============
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
    
    # ============ !unmute ============
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
    
    # ============ !ai on/off ============
    if content.startswith('!ai'):
        parts = content.split(' ', 1)
        if len(parts) < 2:
            await message.channel.send(f"AI is currently: **{'ON' if config.get('ai_enabled', True) else 'OFF'}**")
            return
        
        if parts[1].lower() in ['on', 'enable', 'true']:
            config['ai_enabled'] = True
            save_config()
            await message.channel.send("✅ AI enabled!")
        elif parts[1].lower() in ['off', 'disable', 'false']:
            config['ai_enabled'] = False
            save_config()
            await message.channel.send("❌ AI disabled!")
        else:
            await message.channel.send("❌ Use: `!ai on` or `!ai off`")
        return
    
    # ============ !autojoin on/off ============
    if content.startswith('!autojoin'):
        parts = content.split(' ', 1)
        if len(parts) < 2:
            await message.channel.send(f"Auto-join VC is currently: **{'ON' if config.get('auto_join_vc', False) else 'OFF'}**")
            return
        
        if parts[1].lower() in ['on', 'enable', 'true']:
            config['auto_join_vc'] = True
            save_config()
            await message.channel.send("✅ Auto-join VC enabled!")
        elif parts[1].lower() in ['off', 'disable', 'false']:
            config['auto_join_vc'] = False
            save_config()
            await message.channel.send("❌ Auto-join VC disabled!")
        else:
            await message.channel.send("❌ Use: `!autojoin on` or `!autojoin off`")
        return
    
    # Unknown DM command
    await message.channel.send(f"❌ Unknown command! Use `!help` for commands.\n\n"
                              f"📱 Available commands:\n"
                              f"`!joindc` - Join server\n"
                              f"`!joinvc` - Join VC\n"
                              f"`!leavevc` - Leave VC\n"
                              f"`!servers` - List servers\n"
                              f"`!status` - Bot status\n"
                              f"`!invite` - Get invite link\n"
                              f"`!help` - Show this help")

# ============ SERVER VOICE COMMANDS ============
async def handle_join_vc(message):
    """Handle !joinvc command from server"""
    try:
        if not message.author.voice:
            await message.channel.send("❌ You're not in a voice channel! Join one first.")
            return
        
        channel = message.author.voice.channel
        
        # Check if already connected
        if message.guild.id in voice_connections:
            vc = voice_connections[message.guild.id]
            if vc and vc.is_connected():
                await vc.move_to(channel)
                await message.channel.send(f"🔊 Moved to **{channel.name}**")
                return
        
        # Connect
        vc = await channel.connect(timeout=30.0)
        voice_connections[message.guild.id] = vc
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        
        await message.channel.send(f"🔊 Joined **{channel.name}**!\n- {BOT_CREATOR} | {BOT_OWNER}")
        
    except Exception as e:
        await message.channel.send(f"❌ Failed to join VC: {str(e)[:50]}")

@bot.command(name='joinvc')
async def joinvc_cmd(ctx):
    """Join voice channel (server command)"""
    await handle_join_vc(ctx.message)

@bot.command(name='leavevc')
async def leavevc_cmd(ctx):
    """Leave voice channel (server command)"""
    try:
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc and vc.is_connected():
                await vc.disconnect()
                del voice_connections[ctx.guild.id]
                await ctx.send(f"🔇 Left voice channel\n- {BOT_CREATOR} | {BOT_OWNER}")
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
                await ctx.send("🔇 Bot muted\n- {BOT_CREATOR} | {BOT_OWNER}")
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
                await ctx.send("🔊 Bot unmuted\n- {BOT_CREATOR} | {BOT_OWNER}")
            else:
                await ctx.send("❌ Not in any voice channel!")
        else:
            await ctx.send("❌ Not in any voice channel!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:50]}")

# ============ AI COMMANDS (Server) ============
@bot.command(name='ai')
async def ai_cmd(ctx, *, question):
    """Ask AI"""
    if len(question) > 1000:
        await ctx.send("❌ Too long!")
        return
    
    async with ctx.typing():
        parts = await ask_ai(question)
        await send_part_by_part(ctx.channel, parts)

@bot.command(name='ask')
async def ask_cmd(ctx, *, question):
    """Ask AI (alias)"""
    await ai_cmd(ctx, question=question)

# ============ BOT COMMANDS ============
@bot.command(name='about')
async def about_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} About {BOT_NAME}",
        description=f"Your AI assistant from **{BOT_OWNER}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="🤖 Name", value=f"{BOT_NAME} ({BOT_NICKNAME})", inline=True)
    embed.add_field(name="👤 Creator", value=BOT_CREATOR, inline=True)
    embed.add_field(name="🌐 Owner", value=BOT_OWNER, inline=True)
    embed.add_field(name="📝 Version", value=BOT_VERSION, inline=True)
    embed.add_field(name="🆔 Bot ID", value=BOT_ID, inline=True)
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
    embed.add_field(name="👤 Creator", value=BOT_CREATOR, inline=True)
    embed.set_footer(text=BOT_OWNER)
    await ctx.send(embed=embed)

@bot.command(name='invite')
async def invite_cmd(ctx):
    """Get bot invite link"""
    await ctx.send(f"🔗 **Invite {BOT_NAME} to your server:**\n"
                  f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`")

@bot.command(name='servers')
async def servers_cmd(ctx):
    """List all servers (owner only)"""
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
    
    if len(bot.guilds) > 15:
        embed.set_footer(text=f"And {len(bot.guilds) - 15} more servers...")
    
    await ctx.send(embed=embed)

# ============ HELP COMMAND ============
@bot.command(name='help')
async def help_cmd(ctx):
    embed = discord.Embed(
        title=f"{BOT_EMOJI} {BOT_NAME} Commands",
        description=f"Your AI Assistant from **{BOT_OWNER}**",
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
              "`!ping` - Check latency\n"
              "`!invite` - Get invite link",
        inline=False
    )
    
    if is_authorized(ctx.author):
        embed.add_field(
            name="🔊 Voice Commands",
            value="`!joinvc` - Join your VC\n"
                  "`!leavevc` - Leave VC\n"
                  "`!mutebot` - Mute bot\n"
                  "`!unmutebot` - Unmute bot\n"
                  "`!servers` - List servers",
            inline=False
        )
        
        embed.add_field(
            name="📱 DM Commands (DM Only)",
            value="`!joindc <invite>` - Join server\n"
                  "`!servers` - List servers\n"
                  "`!status` - Bot status\n"
                  "`!invite` - Get invite link\n"
                  "`!joinvc [server_id]` - Join VC\n"
                  "`!leavevc [server_id]` - Leave VC\n"
                  "`!ai on/off` - Toggle AI\n"
                  "`!autojoin on/off` - Auto VC join",
            inline=False
        )
    
    embed.add_field(
        name="🆔 Bot Info",
        value=f"**Bot ID:** `{BOT_ID}`\n"
              f"**Invite Link:**\n"
              f"`https://discord.com/api/oauth2/authorize?client_id={BOT_ID}&permissions=8&scope=bot`",
        inline=False
    )
    
    embed.add_field(
        name="💡 Info",
        value=f"**Creator:** {BOT_CREATOR}\n**Owner:** {BOT_OWNER}\n**Version:** {BOT_VERSION}",
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
║     🤖 {BOT_NAME} v{BOT_VERSION}                             
║                                                              ║
║     👤 Creator: {BOT_CREATOR}                               
║     🌐 Owner: {BOT_OWNER}                                   
║     📝 Version: {BOT_VERSION}                               
║     🆔 Bot ID: {BOT_ID}                                     
║                                                              ║
║     📱 DM Control: {', '.join(AUTHORIZED_USERS)}            
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
