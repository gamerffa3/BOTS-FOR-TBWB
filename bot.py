# bot.py - Complete Discord Bot with Smart AI, Full Control & Multi-Language Support
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
MIN_INTERVAL = 60

# ============ GLOBAL VARIABLES ============
voice_connections = {}
user_sessions = {}
warnings = {}
muted = {}
spam_tracker = {}
config = {}
_bot_ready = False
server_owner_ids = {}

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
        'ai_enabled': True,
        'ai_response_length': 1500
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

# ============ SPLIT RESPONSE ============
def split_response(text, max_length=1900):
    """Smart split - keeps paragraphs together"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current = ""
    
    # Split by sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_length:
            current += sentence + " "
        else:
            if current:
                parts.append(current.strip())
            current = sentence + " "
    
    if current:
        parts.append(current.strip())
    
    return parts

# ============ AI FUNCTION ============
def ask_ai(prompt):
    """Ask AI with smart responses"""
    global last_request_time
    
    if not GH_TOKEN:
        return ["❌ GitHub Token not configured!"]
    
    if not config.get('ai_enabled', True):
        return ["❌ AI features disabled by admin"]
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < MIN_INTERVAL:
        wait_time = MIN_INTERVAL - time_since_last
        logger.info(f"⏳ Waiting {wait_time:.0f} seconds...")
        time.sleep(wait_time)
    
    try:
        url = "https://models.inference.ai.azure.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": f"""You are {BOT_NAME}, an AI assistant created by {CREATOR}.
                Important Rules:
                1. Always respond in the SAME language as the user's question
                2. Keep responses SHORT and CLEAR (maximum 500 words)
                3. Use simple, easy to understand language
                4. Be helpful, friendly and professional
                5. If the user speaks Hindi/Urdu/Roman Hindi, respond in the same language
                6. Break complex answers into simple points"""},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        logger.info(f"📤 Using model: {DEFAULT_MODEL}")
        logger.info(f"📤 Prompt: {prompt[:100]}...")
        
        last_request_time = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        logger.info(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0]["message"]["content"]
                return split_response(text)
            else:
                return ["❌ No response from AI"]
        elif response.status_code == 429:
            logger.warning("⚠️ Rate limit hit, waiting...")
            time.sleep(60)
            return ask_ai(prompt)
        else:
            return [f"❌ API Error: {response.status_code}"]
            
    except requests.Timeout:
        return ["⏰ Timeout! Please try again."]
    except Exception as e:
        logger.error(f"❌ Exception: {str(e)}")
        return [f"❌ Error: {str(e)[:100]}"]

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    global _bot_ready
    if _bot_ready:
        return
    _bot_ready = True
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ✅ {BOT_NAME} is ONLINE!                                 ║
║                                                              ║
║     🤖 Bot: {BOT_NAME}                                      
║     👤 Creator: {CREATOR}                                   
║     🌐 Owner: {OWNER}                                       
║     📊 Servers: {len(bot.guilds)}                           
║     🤖 AI Model: {DEFAULT_MODEL}                            
║     📝 Version: {VERSION}                                   
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"✅ Bot ready! Logged in as {bot.user}")
    
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
    
    # ===== AI REPLY ON TAG =====
    if bot.user.mentioned_in(message):
        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if not prompt:
            await message.reply(f"👋 Hello! I'm {BOT_NAME}. Ask me anything! 🤖\n- By {CREATOR}")
            return
        
        logger.info(f"📥 Tag from {message.author.name}: {prompt[:100]}...")
        
        async with message.channel.typing():
            responses = ask_ai(prompt)
            
            # Send all parts
            for i, part in enumerate(responses):
                if len(responses) > 1:
                    footer = f"\n- By {CREATOR} ({i+1}/{len(responses)})"
                else:
                    footer = f"\n- By {CREATOR}"
                
                await message.reply(f"🤖 {part}{footer}")
        return
    
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!help`", delete_after=5)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission!", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing: {error.param}", delete_after=5)
    else:
        logger.error(f"❌ Command Error: {error}")
        await ctx.send(f"❌ Error: {str(error)[:100]}", delete_after=5)

# ============ OWNER/SERVER OWNER COMMANDS ============
@bot.command(name='setowner')
async def set_owner(ctx, member: discord.Member):
    """Set bot owner (Server Owner only)"""
    if not is_server_owner(ctx.author):
        await ctx.send("❌ Only server owner can set bot owner!")
        return
    
    config['owner_id'] = member.id
    save_config()
    await ctx.send(f"✅ {member.mention} is now the bot owner!")

@bot.command(name='owner')
async def owner_info(ctx):
    """Show bot owner"""
    owner_id = config.get('owner_id')
    if owner_id:
        owner = bot.get_user(owner_id)
        if owner:
            await ctx.send(f"👑 Bot Owner: {owner.mention}")
        else:
            await ctx.send(f"👑 Bot Owner ID: {owner_id}")
    else:
        server_owner = ctx.guild.owner
        await ctx.send(f"👑 Server Owner: {server_owner.mention}")

# ============ SERVER OWNER ONLY COMMANDS ============
@bot.command(name='serverlock')
async def server_lock(ctx):
    """Lock server (Server Owner only)"""
    if not is_server_owner(ctx.author):
        await ctx.send("❌ Only server owner can lock the server!")
        return
    
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        except:
            continue
    
    embed = discord.Embed(
        title="🔒 Server Locked!",
        description="Server has been locked by the owner.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name='serverunlock')
async def server_unlock(ctx):
    """Unlock server (Server Owner only)"""
    if not is_server_owner(ctx.author):
        await ctx.send("❌ Only server owner can unlock the server!")
        return
    
    for channel in ctx.guild.channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        except:
            continue
    
    embed = discord.Embed(
        title="🔓 Server Unlocked!",
        description="Server has been unlocked by the owner.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ============ MODERATION COMMANDS ============
@bot.command(name='warn')
async def warn_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if is_admin(member) or is_server_owner(member):
        await ctx.send("❌ Can't warn this user!", delete_after=5)
        return
    
    if member.id not in warnings:
        warnings[member.id] = []
    
    warnings[member.id].append({
        'reason': reason,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'mod': ctx.author.name
    })
    
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"{member.mention} warned!",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Total", value=len(warnings[member.id]))
    embed.add_field(name="Moderator", value=ctx.author.mention)
    embed.set_footer(text=f"By {CREATOR}")
    await ctx.send(embed=embed)
    
    if len(warnings[member.id]) >= config.get('max_warnings', 3):
        await mute_user(member, config.get('auto_mute_time', 300), "Max warnings")

@bot.command(name='warnings')
async def view_warnings(ctx, member: discord.Member):
    if not is_mod(ctx.author):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if member.id not in warnings or not warnings[member.id]:
        await ctx.send(f"✅ {member.mention} has no warnings!")
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.name}",
        color=discord.Color.orange()
    )
    embed.add_field(name="Total", value=len(warnings[member.id]), inline=False)
    
    for i, warn in enumerate(warnings[member.id][-5:], 1):
        embed.add_field(
            name=f"Warning #{i}",
            value=f"Reason: {warn['reason']}\nTime: {warn['time']}\nBy: {warn['mod']}",
            inline=False
        )
    embed.set_footer(text=f"By {CREATOR}")
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
                        send_messages=False, speak=False, 
                        add_reactions=False, connect=False)
                except:
                    continue
        
        muted[member.id] = {
            'end': datetime.now() + timedelta(seconds=time),
            'reason': reason
        }
        await member.add_roles(mute_role, reason=f"Muted: {reason}")
        
        async def unmute_task():
            await asyncio.sleep(time)
            if member.id in muted:
                try:
                    await member.remove_roles(mute_role, reason="Auto unmute")
                    del muted[member.id]
                except:
                    pass
        
        bot.loop.create_task(unmute_task())
        return True
    except:
        return False

@bot.command(name='mute')
async def mute_cmd(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    if not is_mod(ctx.author):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if is_admin(member) or is_server_owner(member):
        await ctx.send("❌ Can't mute this user!", delete_after=5)
        return
    
    if time < 1 or time > 86400:
        await ctx.send("❌ Time must be 1-86400 seconds!", delete_after=5)
        return
    
    if await mute_user(member, time, reason):
        embed = discord.Embed(
            title="🔇 User Muted",
            color=discord.Color.red()
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Time", value=f"{time} seconds")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.set_footer(text=f"By {CREATOR}")
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Failed to mute!", delete_after=5)

@bot.command(name='unmute')
async def unmute_cmd(ctx, member: discord.Member):
    if not is_mod(ctx.author):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if mute_role:
            await member.remove_roles(mute_role)
        del muted[member.id]
        
        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"{member.mention} unmuted!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"By {CREATOR}")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {member.mention} is not muted!")

@bot.command(name='kick')
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if is_admin(member) or is_server_owner(member) or member.bot:
        await ctx.send("❌ Can't kick this user!", delete_after=5)
        return
    
    try:
        await member.kick(reason=f"{reason} - By {ctx.author.name}")
        embed = discord.Embed(title="👢 User Kicked", color=discord.Color.red())
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.set_footer(text=f"By {CREATOR}")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")

@bot.command(name='ban')
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if is_admin(member) or is_server_owner(member) or member.bot:
        await ctx.send("❌ Can't ban this user!", delete_after=5)
        return
    
    try:
        await member.ban(reason=f"{reason} - By {ctx.author.name}")
        embed = discord.Embed(title="🔨 User Banned", color=discord.Color.red())
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.set_footer(text=f"By {CREATOR}")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        await ctx.send("❌ Amount must be 1-100!", delete_after=5)
        return
    
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages! - By {CREATOR}")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")

# ============ AI COMMANDS ============
@bot.command(name='ai')
async def ai_command(ctx, *, question):
    """Ask AI anything - Smart & Short"""
    if len(question) > 1000:
        await ctx.send("❌ Too long! Max 1000 characters.")
        return
    
    logger.info(f"📥 !ai from {ctx.author.name}: {question[:100]}...")
    
    async with ctx.typing():
        responses = ask_ai(question)
        
        for i, part in enumerate(responses):
            if len(responses) > 1:
                footer = f"\n- By {CREATOR} ({i+1}/{len(responses)})"
            else:
                footer = f"\n- By {CREATOR}"
            await ctx.send(f"🤖 {part}{footer}")

# ============ SETUP COMMANDS ============
@bot.command(name='setlog')
@commands.has_permissions(administrator=True)
async def set_log(ctx, channel: discord.TextChannel):
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f"✅ Log channel set to {channel.mention}")

@bot.command(name='setmodrole')
@commands.has_permissions(administrator=True)
async def set_mod_role(ctx, role: discord.Role):
    if role.id not in config.get('mod_roles', []):
        config['mod_roles'].append(role.id)
        save_config()
        await ctx.send(f"✅ {role.mention} added as mod role")

@bot.command(name='removemodrole')
@commands.has_permissions(administrator=True)
async def remove_mod_role(ctx, role: discord.Role):
    if role.id in config.get('mod_roles', []):
        config['mod_roles'].remove(role.id)
        save_config()
        await ctx.send(f"❌ {role.mention} removed from mod roles")

@bot.command(name='setadminrole')
@commands.has_permissions(administrator=True)
async def set_admin_role(ctx, role: discord.Role):
    if role.id not in config.get('admin_roles', []):
        config['admin_roles'].append(role.id)
        save_config()
        await ctx.send(f"✅ {role.mention} added as admin role")

@bot.command(name='removeadminrole')
@commands.has_permissions(administrator=True)
async def remove_admin_role(ctx, role: discord.Role):
    if role.id in config.get('admin_roles', []):
        config['admin_roles'].remove(role.id)
        save_config()
        await ctx.send(f"❌ {role.mention} removed from admin roles")

@bot.command(name='aitoggle')
@commands.has_permissions(administrator=True)
async def toggle_ai(ctx):
    config['ai_enabled'] = not config.get('ai_enabled', True)
    save_config()
    status = "✅ Enabled" if config['ai_enabled'] else "❌ Disabled"
    await ctx.send(f"AI features: **{status}**")

# ============ VOICE COMMANDS ============
@bot.command(name='join')
async def join_vc(ctx, channel_id: int = None):
    """Bot ko VC mein join karo (muted)"""
    if not is_mod(ctx.author):
        await ctx.send("❌ Only mods can use this command!")
        return
    
    try:
        if channel_id:
            channel = bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await ctx.send("❌ Invalid voice channel ID!")
                return
        else:
            if not ctx.author.voice:
                await ctx.send("❌ You're not in a VC!")
                return
            channel = ctx.author.voice.channel
        
        if ctx.guild.id in voice_connections:
            try:
                await voice_connections[ctx.guild.id].disconnect()
                del voice_connections[ctx.guild.id]
            except:
                pass
        
        vc = await channel.connect()
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        voice_connections[ctx.guild.id] = vc
        
        await ctx.send(f"🔊 Joined {channel.mention} (Muted) - By {CREATOR}")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='leave')
async def leave_vc(ctx):
    """Bot ko VC se nikalo"""
    if not is_mod(ctx.author):
        await ctx.send("❌ Only mods can use this command!")
        return
    
    try:
        if ctx.guild.id in voice_connections:
            await voice_connections[ctx.guild.id].disconnect()
            del voice_connections[ctx.guild.id]
            await ctx.send(f"✅ Left VC - By {CREATOR}")
        else:
            await ctx.send("❌ Bot is not in any VC!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

# ============ INFO COMMANDS ============
@bot.command(name='ping')
async def ping_command(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: **{latency}ms**\n- By {CREATOR}")

@bot.command(name='test')
async def test_command(ctx):
    await ctx.send(f"✅ Bot is working! Connected as {bot.user}\n- By {CREATOR}")

@bot.command(name='stats')
async def stats_command(ctx):
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=discord.Color.blue()
    )
    embed.add_field(name="🤖 Bot", value=BOT_NAME)
    embed.add_field(name="👤 Creator", value=CREATOR)
    embed.add_field(name="🌐 Owner", value=OWNER)
    embed.add_field(name="📊 Servers", value=len(bot.guilds))
    embed.add_field(name="⚡ Latency", value=f"{round(bot.latency * 1000)}ms")
    embed.add_field(name="🤖 AI Status", value="✅ Enabled" if config.get('ai_enabled', True) else "❌ Disabled")
    embed.set_footer(text=f"{OWNER} • {BOT_NAME}")
    await ctx.send(embed=embed)

@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME} Commands",
        description=f"Created by **{CREATOR}** • **{OWNER}**",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📌 Tag Bot",
        value=f"`@{BOT_NAME} <question>` - Ask AI in any language",
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI Commands",
        value="`!ai <question>` - Smart AI responses\n"
              "`!test` - Test bot\n"
              "`!ping` - Check latency",
        inline=False
    )
    
    if is_mod(ctx.author) or is_server_owner(ctx.author):
        embed.add_field(
            name="🛡️ Moderation",
            value="`!warn @user <reason>` - Warn\n"
                  "`!warnings @user` - View warnings\n"
                  "`!mute @user <time> <reason>` - Mute\n"
                  "`!unmute @user` - Unmute\n"
                  "`!kick @user <reason>` - Kick\n"
                  "`!ban @user <reason>` - Ban\n"
                  "`!clear <amount>` - Clear messages\n"
                  "`!join` - Join VC\n"
                  "`!leave` - Leave VC",
            inline=False
        )
    
    if is_admin(ctx.author) or is_server_owner(ctx.author):
        embed.add_field(
            name="⚙️ Admin",
            value="`!setowner @user` - Set bot owner\n"
                  "`!setlog #channel` - Set log channel\n"
                  "`!setmodrole @role` - Add mod role\n"
                  "`!removemodrole @role` - Remove mod role\n"
                  "`!setadminrole @role` - Add admin role\n"
                  "`!removeadminrole @role` - Remove admin role\n"
                  "`!aitoggle` - Enable/Disable AI\n"
                  "`!serverlock` - Lock server\n"
                  "`!serverunlock` - Unlock server",
            inline=False
        )
    
    embed.add_field(
        name="ℹ️ Info",
        value="`!stats` - Bot statistics\n"
              "`!owner` - Show bot owner\n"
              "`!help` - Show this menu",
        inline=False
    )
    
    embed.set_footer(text=f"Powered by DeepSeek-R1 • {OWNER}")
    await ctx.send(embed=embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        print("🤖 Starting CAREFULLY Bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"❌ Fatal Error: {e}")