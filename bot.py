# bot.py - Complete Working with Short Messages & No Timeout
import os
import discord
from discord.ext import commands
import requests
import json
import logging
import sys
import asyncio
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict

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

# ============ BOT INFO ============
BOT_NAME = "CAREFULLY"
CREATOR = "TurboIG"
OWNER = "TurboIG Web"
VERSION = "2.0.0"
DEFAULT_MODEL = "DeepSeek-R1"

# ============ RATE LIMIT ============
last_request_time = 0
MIN_INTERVAL = 30

# ============ GLOBAL VARIABLES ============
voice_connections = {}
user_sessions = {}
warnings = {}
muted = {}
spam_tracker = {}
config = {}
_bot_ready = False

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
        'welcome_channel': None,
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

# ============ SHORT MESSAGE HELPER ============
def make_short(text, max_len=300):
    """Make text short"""
    if len(text) <= max_len:
        return text
    
    # Try to cut at sentence end
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = ""
    for sent in sentences:
        if len(result) + len(sent) + 1 <= max_len:
            result += sent + " "
        else:
            break
    
    if result:
        return result.strip() + "..."
    else:
        return text[:max_len] + "..."

# ============ SMART SPLIT ============
def split_smart(text, max_len=1500):
    """Smart split into small parts"""
    if len(text) <= max_len:
        return [text]
    
    parts = []
    current = ""
    
    # Split by paragraphs
    for para in text.split('\n\n'):
        if len(current) + len(para) + 2 <= max_len:
            current += para + "\n\n"
        else:
            if current:
                parts.append(current.strip())
            # Split long paragraph
            if len(para) > max_len:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= max_len:
                        current += sent + " "
                    else:
                        if current:
                            parts.append(current.strip())
                        current = sent + " "
            else:
                current = para + "\n\n"
    
    if current:
        parts.append(current.strip())
    
    # Limit parts
    if len(parts) > 3:
        # Combine last parts
        combined = []
        for part in parts:
            if len(combined) > 0 and len(combined[-1]) + len(part) + 1 <= max_len:
                combined[-1] += "\n\n" + part
            else:
                combined.append(part)
        parts = combined
    
    return parts

# ============ ASYNC AI FUNCTION ============
async def ask_ai(prompt):
    """Ask AI - short responses only"""
    global last_request_time
    
    if not GH_TOKEN:
        return ["❌ GitHub Token not configured!"]
    
    if not config.get('ai_enabled', True):
        return ["❌ AI disabled by admin"]
    
    # Rate limit
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < MIN_INTERVAL:
        wait_time = MIN_INTERVAL - time_since_last
        logger.info(f"⏳ Waiting {wait_time:.0f}s...")
        await asyncio.sleep(wait_time)
    
    try:
        url = "https://models.inference.ai.azure.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": f"""You are {BOT_NAME}. IMPORTANT RULES:
                1. Respond in SAME language as user
                2. MAX 150 words - be VERY BRIEF
                3. Give direct answers, no extra fluff
                4. If question is complex, give SUMMARY only
                5. Be friendly but concise"""},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200,
            "temperature": 0.6
        }
        
        logger.info(f"📤 Prompt: {prompt[:80]}...")
        
        last_request_time = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0]["message"]["content"]
                # Make it short
                short_text = make_short(text, 500)
                parts = split_smart(short_text)
                return parts
            else:
                return ["❌ No response"]
        elif response.status_code == 429:
            await asyncio.sleep(60)
            return await ask_ai(prompt)
        else:
            return [f"❌ Error: {response.status_code}"]
            
    except requests.Timeout:
        return ["⏰ Timeout! Try again."]
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return [f"❌ Error"]

# ============ SEND MESSAGES ============
async def send_parts(channel, parts, user_mention=None):
    """Send message parts one by one"""
    total = len(parts)
    
    for i, part in enumerate(parts):
        if not part or part.strip() == "":
            continue
            
        if total > 1:
            footer = f"\n📄 {i+1}/{total}"
        else:
            footer = ""
        
        content = f"🤖 {part}{footer}\n- By {CREATOR}"
        
        if len(content) > 2000:
            # Split if too long
            for j in range(0, len(content), 1900):
                await channel.send(content[j:j+1900])
        else:
            await channel.send(content)
        
        # Small delay between parts
        if i < len(parts) - 1:
            await asyncio.sleep(0.3)

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    global _bot_ready
    if _bot_ready:
        return
    _bot_ready = True
    
    print(f"""
✅ {BOT_NAME} ONLINE!
📊 {len(bot.guilds)} Servers
🤖 Model: {DEFAULT_MODEL}
""")
    
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
            await message.channel.send(f"👋 Hello! I'm {BOT_NAME}. Ask me anything! 🤖\n- By {CREATOR}")
            return
        
        logger.info(f"📥 Tag: {prompt[:80]}...")
        
        async with message.channel.typing():
            parts = await ask_ai(prompt)
            await send_parts(message.channel, parts)
        return
    
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!help`", delete_after=5)
    else:
        await ctx.send(f"❌ Error", delete_after=5)

# ============ COMMANDS ============
@bot.command(name='ai')
async def ai_cmd(ctx, *, question):
    """Ask AI"""
    if len(question) > 1000:
        await ctx.send("❌ Too long!")
        return
    
    async with ctx.typing():
        parts = await ask_ai(question)
        await send_parts(ctx.channel, parts)

@bot.command(name='ping')
async def ping_cmd(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency*1000)}ms")

@bot.command(name='test')
async def test_cmd(ctx):
    await ctx.send(f"✅ Bot working!\n- By {CREATOR}")

@bot.command(name='help')
async def help_cmd(ctx):
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME}",
        description=f"By {CREATOR} • {OWNER}",
        color=discord.Color.blue()
    )
    embed.add_field(name="📌 Tag", value=f"`@{BOT_NAME} <question>`", inline=False)
    embed.add_field(name="🤖 AI", value="`!ai <question>`", inline=False)
    embed.add_field(name="ℹ️ Info", value="`!ping` `!test` `!help`", inline=False)
    
    if is_mod(ctx.author):
        embed.add_field(name="🛡️ Mod", value="`!warn @user` `!mute @user` `!kick` `!ban` `!clear`", inline=False)
    
    if is_admin(ctx.author) or is_server_owner(ctx.author):
        embed.add_field(name="⚙️ Admin", value="`!setowner @user` `!serverlock` `!serverunlock`", inline=False)
    
    await ctx.send(embed=embed)

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
    await ctx.send(embed=embed)
    
    if len(warnings[member.id]) >= config.get('max_warnings', 3):
        await mute_user(member, config.get('auto_mute_time', 300), "Max warnings")

@bot.command(name='warnings')
async def warnings_cmd(ctx, member: discord.Member):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    if member.id not in warnings or not warnings[member.id]:
        return await ctx.send(f"✅ {member.mention} no warnings!")
    
    embed = discord.Embed(title=f"⚠️ Warnings for {member.name}", color=discord.Color.orange())
    embed.add_field(name="Total", value=len(warnings[member.id]), inline=False)
    
    for i, warn in enumerate(warnings[member.id][-5:], 1):
        embed.add_field(name=f"#{i}", value=f"{warn['reason']}\n{warn['time']}", inline=False)
    
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
                    await channel.set_permissions(mute_role, send_messages=False, speak=False, connect=False)
                except:
                    continue
        
        muted[member.id] = {'end': datetime.now() + timedelta(seconds=time), 'reason': reason}
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
    
    if await mute_user(member, time, reason):
        await ctx.send(f"🔇 {member.mention} muted for {time}s\n- By {CREATOR}")
    else:
        await ctx.send("❌ Failed!")

@bot.command(name='unmute')
async def unmute_cmd(ctx, member: discord.Member):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if mute_role:
            await member.remove_roles(mute_role)
        del muted[member.id]
        await ctx.send(f"🔊 {member.mention} unmuted!")
    else:
        await ctx.send(f"❌ Not muted!")

@bot.command(name='kick')
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} kicked!\n- By {CREATOR}")
    except:
        await ctx.send("❌ Failed!")

@bot.command(name='ban')
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} banned!\n- By {CREATOR}")
    except:
        await ctx.send("❌ Failed!")

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ 1-100 only!")
    try:
        deleted = await ctx.channel.purge(limit=amount+1)
        msg = await ctx.send(f"✅ Deleted {len(deleted)-1}!")
        await asyncio.sleep(2)
        await msg.delete()
    except:
        await ctx.send("❌ Failed!")

# ============ VOICE COMMANDS ============
@bot.command(name='join')
async def join_cmd(ctx, channel_id: int = None):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    try:
        if channel_id:
            channel = bot.get_channel(channel_id)
        else:
            if not ctx.author.voice:
                return await ctx.send("❌ You're not in VC!")
            channel = ctx.author.voice.channel
        
        if ctx.guild.id in voice_connections:
            await voice_connections[ctx.guild.id].disconnect()
        
        vc = await channel.connect()
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        voice_connections[ctx.guild.id] = vc
        await ctx.send(f"🔊 Joined {channel.name} (Muted)")
    except:
        await ctx.send("❌ Failed!")

@bot.command(name='leave')
async def leave_cmd(ctx):
    if not is_mod(ctx.author):
        return await ctx.send("❌ No permission!")
    try:
        if ctx.guild.id in voice_connections:
            await voice_connections[ctx.guild.id].disconnect()
            del voice_connections[ctx.guild.id]
            await ctx.send("✅ Left VC")
        else:
            await ctx.send("❌ Not in VC")
    except:
        await ctx.send("❌ Failed!")

# ============ ADMIN COMMANDS ============
@bot.command(name='setowner')
async def setowner_cmd(ctx, member: discord.Member):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Server owner only!")
    config['owner_id'] = member.id
    save_config()
    await ctx.send(f"✅ {member.mention} is bot owner!")

@bot.command(name='serverlock')
async def serverlock_cmd(ctx):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Server owner only!")
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        except:
            continue
    await ctx.send("🔒 Server Locked!")

@bot.command(name='serverunlock')
async def serverunlock_cmd(ctx):
    if not is_server_owner(ctx.author):
        return await ctx.send("❌ Server owner only!")
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        except:
            continue
    await ctx.send("🔓 Server Unlocked!")

# ============ RUN ============
if __name__ == "__main__":
    try:
        print("🤖 Starting bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")