# bot.py - Complete Production Ready Bot with Auto-Install & Single Message (A to Z)
import subprocess
import sys
import os

# ============ AUTO-INSTALL DEPENDENCIES (RUNS ONCE) ============
def install_packages():
    """Auto-install required packages - runs only once per session"""
    packages = ['discord.py', 'pynacl', 'aiohttp']
    needs_install = False
    
    print("🔍 Checking dependencies...")
    for package in packages:
        try:
            if package == 'discord.py':
                __import__('discord')
            elif package == 'pynacl':
                __import__('nacl')
            elif package == 'aiohttp':
                __import__('aiohttp')
            print(f"✅ {package} already installed")
        except ImportError:
            needs_install = True
            break
    
    if needs_install:
        print("📦 Installing missing packages...")
        for package in packages:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
                print(f"✅ {package} installed!")
            except Exception as e:
                print(f"❌ Failed to install {package}: {e}")
        print("✅ All dependencies ready!\n")
    else:
        print("✅ All dependencies already installed!\n")

# Run auto-install ONCE
install_packages()

# ============ IMPORTS ============
import discord
from discord.ext import commands
import asyncio
import re
import json
import time
from datetime import datetime, timedelta
import logging
from collections import defaultdict

# ============ SETUP ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
    print("💡 Please set DISCORD_TOKEN in environment variables")
    exit(1)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============ GLOBAL VARIABLES ============
config = {}
warnings = {}
muted = {}
spam_tracker = {}
ping_tracker = {}
link_whitelist = []
role_whitelist = []
user_whitelist = []
voice_connections = {}
join_tracker = defaultdict(list)
suspicious_links = ['discord.gift', 'steamcommunity.com', 'free', 'nitro', 'giveaway']

# ============ PREVENT MULTIPLE MESSAGES ============
_bot_ready = False  # Track if bot already sent ready message
_startup_time = datetime.now()

# ============ PERSISTENT CONFIG MANAGEMENT ============
def load_config():
    """Load config from file - PERSISTENT"""
    global config
    config_file = 'config.json'
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info("✅ Config loaded from file")
            return
        except Exception as e:
            logger.warning(f"⚠️ Config load error: {e}")
    
    # Create default config
    config = {
        'log_channel': None,
        'mute_channel': None,
        'auto_mute_time': 300,
        'max_warnings': 3,
        'spam_threshold': 5,
        'spam_timeframe': 5,
        'ping_threshold': 3,
        'ping_timeframe': 10,
        'join_threshold': 5,
        'join_timeframe': 60,
        'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 
                     'benchod', 'bhak', 'bsdk', 'fuck', 'shit', 'asshole'],
        'mod_roles': [],
        'admin_roles': [],
        'protected_roles': []
    }
    save_config()
    logger.info("✅ Default config created")

def save_config():
    """Save config to file - PERSISTENT"""
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        logger.info("✅ Config saved to file")
    except Exception as e:
        logger.error(f"❌ Config save error: {e}")

# Load config on startup
load_config()

# ============ PERMISSION CHECKS ============
def is_admin(member):
    if not member:
        return False
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
    if is_admin(member):
        return True
    if hasattr(member, 'guild_permissions') and member.guild_permissions.manage_messages:
        return True
    if hasattr(member, 'roles'):
        for role in member.roles:
            if role.id in config.get('mod_roles', []):
                return True
    return False

def is_whitelisted(member):
    if not member:
        return False
    if is_admin(member):
        return True
    if member.id in user_whitelist:
        return True
    if hasattr(member, 'roles'):
        for role in member.roles:
            if role.id in role_whitelist:
                return True
    return False

def has_mod_perms(ctx):
    if not ctx or not ctx.author:
        return False
    return is_mod(ctx.author) or ctx.author.guild_permissions.manage_messages

def has_admin_perms(ctx):
    if not ctx or not ctx.author:
        return False
    return is_admin(ctx.author) or ctx.author.guild_permissions.administrator

# ============ LOGGING ============
async def log_event(guild, embed):
    if not guild:
        return
    channel_id = config.get('log_channel')
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

# ============ MUTE SYSTEM ============
async def mute_user(member, time, reason="No reason"):
    try:
        if not member or is_admin(member) or member == member.guild.owner:
            return False
        
        muted[member.id] = {
            'end': datetime.now() + timedelta(seconds=time),
            'reason': reason
        }
        
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if not mute_role:
            try:
                mute_role = await member.guild.create_role(name="Muted")
                for channel in member.guild.channels:
                    try:
                        await channel.set_permissions(mute_role, 
                            send_messages=False, speak=False, 
                            add_reactions=False, connect=False)
                    except:
                        continue
            except:
                return False
        
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

# ============ ANTI-RAID SYSTEM ============
async def check_raid(guild, member):
    current_time = time.time()
    join_tracker[guild.id].append((member.id, current_time))
    
    join_tracker[guild.id] = [(uid, t) for uid, t in join_tracker[guild.id] 
                              if current_time - t < config.get('join_timeframe', 60)]
    
    if len(join_tracker[guild.id]) >= config.get('join_threshold', 5):
        log_channel = guild.get_channel(config.get('log_channel'))
        if log_channel:
            embed = discord.Embed(
                title="⚠️ RAID DETECTED!",
                description=f"**{len(join_tracker[guild.id])} members joined in {config.get('join_timeframe', 60)} seconds!**",
                color=discord.Color.red()
            )
            await log_channel.send(embed=embed)
        
        try:
            for channel in guild.channels:
                try:
                    await channel.set_permissions(guild.default_role, 
                        send_messages=False, create_instant_invite=False)
                except:
                    continue
            
            if log_channel:
                embed = discord.Embed(
                    title="🔒 Server Locked!",
                    description="Server locked due to suspected raid. Please investigate.",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=embed)
        except:
            pass
        
        return True
    return False

# ============ VOICE COMMANDS ============
@bot.command(name='join')
async def join_vc(ctx, channel_id: int):
    """Bot ko VC mein join karo (mute rahega)"""
    try:
        if not ctx.author.voice:
            await ctx.send("❌ Aap khud VC mein nahi ho! Pehle VC join karo.")
            return
        
        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("❌ Invalid channel ID! Sahi VC ID do.")
            return
        
        if not isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ Yeh voice channel nahi hai! Voice channel ID do.")
            return
        
        if ctx.guild.id in voice_connections:
            try:
                await voice_connections[ctx.guild.id].disconnect()
                del voice_connections[ctx.guild.id]
            except:
                pass
        
        try:
            vc = await channel.connect()
            await vc.guild.change_voice_state(channel=channel, self_mute=True)
            voice_connections[ctx.guild.id] = vc
            
            embed = discord.Embed(
                title="🔊 Bot Joined Voice Channel",
                description=f"Joined {channel.mention} (🔇 Muted)",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=channel.name)
            embed.add_field(name="Status", value="Muted")
            embed.add_field(name="Requested by", value=ctx.author.mention)
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error joining VC: {str(e)[:100]}")
            if "PyNaCl" in str(e):
                await ctx.send("💡 Installing PyNaCl... Please wait and try again.")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pynacl", "--quiet"])
                await ctx.send("✅ PyNaCl installed! Try `!join` again.")
        
    except discord.Forbidden:
        await ctx.send("❌ Bot ko VC join karne ki permission nahi hai!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='leave')
async def leave_vc(ctx):
    """Bot ko VC se nikalo"""
    try:
        if ctx.guild.id in voice_connections:
            await voice_connections[ctx.guild.id].disconnect()
            del voice_connections[ctx.guild.id]
            await ctx.send("✅ Bot left the voice channel!")
        else:
            await ctx.send("❌ Bot kisi VC mein nahi hai!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='vcstatus')
async def vc_status(ctx):
    """Check bot voice status"""
    if ctx.guild.id in voice_connections:
        vc = voice_connections[ctx.guild.id]
        if vc.is_connected():
            embed = discord.Embed(
                title="🎤 Bot Voice Status",
                color=discord.Color.blue()
            )
            embed.add_field(name="Channel", value=vc.channel.mention)
            embed.add_field(name="Connected", value="✅ Yes")
            embed.add_field(name="Muted", value="🔇 Yes" if vc.is_muted() else "🔊 No")
            embed.add_field(name="Members", value=len(vc.channel.members))
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Bot disconnected!")
            del voice_connections[ctx.guild.id]
    else:
        await ctx.send("❌ Bot kisi VC mein nahi hai!")

# ============ CHAT COMMANDS ============
@bot.command(name='hi')
async def send_hi(ctx, channel_id: int, *, message):
    """Kisi specific channel mein message bhejo"""
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("❌ Invalid channel ID! Sahi channel ID do.")
            return
        
        # Check if it's a voice channel - send error
        if isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ Yeh voice channel hai! Text channel ID do. Voice channel mein message nahi bhej sakte.")
            return
        
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await ctx.send("❌ Yeh text channel nahi hai! Text channel ID do.")
            return
        
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages:
            await ctx.send("❌ Bot ko is channel mein message bhejne ki permission nahi!")
            return
        
        await channel.send(message)
        
        embed = discord.Embed(
            title="✅ Message Sent",
            description=f"Sent to {channel.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Message", value=message[:500])
        embed.add_field(name="Channel Type", value="Text Channel")
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='say')
async def say_cmd(ctx, *, message):
    """Current channel mein message bhejo"""
    try:
        await ctx.send(message)
        try:
            await ctx.message.delete()
        except:
            pass
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='announce')
async def announce_cmd(ctx, channel_id: int, *, message):
    """Announcement bhejo"""
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("❌ Invalid channel ID!")
            return
        
        if isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ Voice channel mein announcement nahi bhej sakte! Text channel ID do.")
            return
        
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"By {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await channel.send(embed=embed)
        await ctx.send(f"✅ Announcement sent to {channel.mention}")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    """Called when bot is ready - SINGLE MESSAGE ONLY"""
    global _bot_ready
    
    # Prevent multiple ready messages
    if _bot_ready:
        return
    _bot_ready = True
    
    print(f'✅ Bot is online! Logged in as {bot.user}')
    print(f'📊 Connected to {len(bot.guilds)} servers')
    print(f'⏰ Started at: {_startup_time.strftime("%Y-%m-%d %H:%M:%S")}')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers | !modhelp"
        )
    )
    
    logger.info(f'Bot is ready! Logged in as {bot.user}')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!modhelp`", delete_after=5)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission!", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing: {error.param}", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument!", delete_after=5)
    else:
        logger.error(f"Error: {error}")
        await ctx.send(f"❌ Error: {str(error)[:100]}", delete_after=5)

@bot.event
async def on_member_join(member):
    """Welcome and anti-raid"""
    await check_raid(member.guild, member)
    
    channel = member.guild.system_channel
    if channel:
        embed = discord.Embed(
            title="🙌 Welcome!",
            description=f"{member.mention} Welcome to the server!",
            color=discord.Color.green()
        )
        embed.add_field(name="👤 User", value=member.name)
        embed.add_field(name="📅 Joined", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    """Handle messages with automod"""
    if message.author.bot:
        return
    
    await bot.process_commands(message)
    
    if is_admin(message.author) or is_whitelisted(message.author):
        return
    
    # ===== SPAM DETECTION =====
    current_time = datetime.now()
    if message.author.id not in spam_tracker:
        spam_tracker[message.author.id] = []
    
    spam_tracker[message.author.id] = [
        t for t in spam_tracker[message.author.id] 
        if (current_time - t).seconds < config.get('spam_timeframe', 5)
    ]
    spam_tracker[message.author.id].append(current_time)
    
    if len(spam_tracker[message.author.id]) > config.get('spam_threshold', 5):
        await message.delete()
        await message.channel.send(f"🚫 {message.author.mention} No spam!", delete_after=5)
        if len(spam_tracker[message.author.id]) > 10:
            await mute_user(message.author, 300, "Excessive spam")
        return
    
    # ===== PING SPAM DETECTION =====
    ping_count = len(re.findall(r'<@!?&?\d+>', message.content))
    if ping_count > 0:
        if message.author.id not in ping_tracker:
            ping_tracker[message.author.id] = []
        
        ping_tracker[message.author.id] = [
            t for t in ping_tracker[message.author.id] 
            if (current_time - t).seconds < config.get('ping_timeframe', 10)
        ]
        ping_tracker[message.author.id].append(current_time)
        
        if len(ping_tracker[message.author.id]) > config.get('ping_threshold', 3):
            await message.delete()
            await message.channel.send(f"🚫 {message.author.mention} No ping spam!", delete_after=5)
            return
    
    # ===== BAD WORDS FILTER =====
    for word in config.get('bad_words', []):
        if word.lower() in message.content.lower():
            await message.delete()
            await message.channel.send(f"🚫 {message.author.mention} No bad words!", delete_after=5)
            await mute_user(message.author, 60, "Bad word")
            break
    
    # ===== LINK FILTER =====
    link_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)'
    if re.search(link_pattern, message.content, re.IGNORECASE):
        if message.author.id not in link_whitelist:
            for suspicious in suspicious_links:
                if suspicious in message.content.lower():
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention} Suspicious link detected!", delete_after=5)
                    await mute_user(message.author, 300, "Suspicious link")
                    return
            
            await message.delete()
            await message.channel.send(f"🔗 {message.author.mention} Links blocked!", delete_after=5)

# ============ ANTI-NUKE PROTECTION ============
@bot.event
async def on_guild_channel_delete(channel):
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 600, "Channel delete without permission")
                embed = discord.Embed(
                    title="⚠️ Channel Deleted Without Permission!",
                    color=discord.Color.red()
                )
                embed.add_field(name="User", value=entry.user.mention)
                embed.add_field(name="Channel", value=channel.name)
                embed.add_field(name="Action", value="Muted for 10 minutes")
                await log_event(channel.guild, embed)
                break
    except:
        pass

@bot.event
async def on_guild_channel_create(channel):
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 600, "Channel create without permission")
                embed = discord.Embed(
                    title="⚠️ Channel Created Without Permission!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="User", value=entry.user.mention)
                embed.add_field(name="Channel", value=channel.mention)
                embed.add_field(name="Action", value="Muted for 10 minutes")
                await log_event(channel.guild, embed)
                break
    except:
        pass

@bot.event
async def on_guild_role_create(role):
    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 600, "Role create without permission")
                embed = discord.Embed(
                    title="⚠️ Role Created Without Permission!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="User", value=entry.user.mention)
                embed.add_field(name="Role", value=role.name)
                embed.add_field(name="Action", value="Muted for 10 minutes")
                await log_event(role.guild, embed)
                break
    except:
        pass

@bot.event
async def on_guild_role_delete(role):
    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 600, "Role delete without permission")
                embed = discord.Embed(
                    title="⚠️ Role Deleted Without Permission!",
                    color=discord.Color.red()
                )
                embed.add_field(name="User", value=entry.user.mention)
                embed.add_field(name="Role", value=role.name)
                embed.add_field(name="Action", value="Muted for 10 minutes")
                await log_event(role.guild, embed)
                break
    except:
        pass

@bot.event
async def on_member_update(before, after):
    """Protect against unauthorized permission changes"""
    if before.roles != after.roles:
        for role in after.roles:
            if role not in before.roles:
                try:
                    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                        if entry.user and not is_admin(entry.user):
                            await mute_user(entry.user, 600, "Role add without permission")
                            embed = discord.Embed(
                                title="⚠️ Role Added Without Permission!",
                                color=discord.Color.orange()
                            )
                            embed.add_field(name="User", value=entry.user.mention)
                            embed.add_field(name="Target", value=after.mention)
                            embed.add_field(name="Role", value=role.mention)
                            embed.add_field(name="Action", value="Muted for 10 minutes")
                            await log_event(after.guild, embed)
                            break
                except:
                    pass

# ============ MODERATION COMMANDS ============
@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        await ctx.send("❌ Amount must be 1-100!", delete_after=5)
        return
    
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages!")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")

@bot.command(name='warn')
async def warn_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not has_mod_perms(ctx):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if is_admin(member) or member.bot:
        await ctx.send("❌ Can't warn!", delete_after=5)
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
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)
    
    if len(warnings[member.id]) >= config.get('max_warnings', 3):
        await mute_user(member, config.get('auto_mute_time', 300), "Max warnings")

@bot.command(name='warnings')
async def view_warnings(ctx, member: discord.Member):
    if not has_mod_perms(ctx):
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
    
    await ctx.send(embed=embed)

@bot.command(name='mute')
async def mute_cmd(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    if not has_mod_perms(ctx):
        await ctx.send("❌ No permission!", delete_after=5)
        return
    
    if is_admin(member) or member.bot:
        await ctx.send("❌ Can't mute!", delete_after=5)
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
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send("❌ Failed to mute!", delete_after=5)

@bot.command(name='unmute')
async def unmute_cmd(ctx, member: discord.Member):
    if not has_mod_perms(ctx):
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
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {member.mention} is not muted!")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if is_admin(member) or member.bot:
        await ctx.send("❌ Can't kick!", delete_after=5)
        return
    
    try:
        await member.kick(reason=f"{reason} - By {ctx.author.name}")
        embed = discord.Embed(title="👢 User Kicked", color=discord.Color.red())
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if is_admin(member) or member.bot:
        await ctx.send("❌ Can't ban!", delete_after=5)
        return
    
    try:
        await member.ban(reason=f"{reason} - By {ctx.author.name}")
        embed = discord.Embed(title="🔨 User Banned", color=discord.Color.red())
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")

# ============ ADMIN SETUP COMMANDS ============
@bot.command(name='setlog')
@commands.has_permissions(administrator=True)
async def set_log(ctx, channel: discord.TextChannel):
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f"✅ Log channel set to {channel.mention}")

@bot.command(name='setmute')
@commands.has_permissions(administrator=True)
async def set_mute(ctx, channel: discord.TextChannel):
    config['mute_channel'] = channel.id
    save_config()
    await ctx.send(f"✅ Mute channel set to {channel.mention}")

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

@bot.command(name='setprotectedrole')
@commands.has_permissions(administrator=True)
async def set_protected_role(ctx, role: discord.Role):
    if role.id not in config.get('protected_roles', []):
        config['protected_roles'].append(role.id)
        save_config()
        await ctx.send(f"✅ {role.mention} added as protected role")

@bot.command(name='removeprotectedrole')
@commands.has_permissions(administrator=True)
async def remove_protected_role(ctx, role: discord.Role):
    if role.id in config.get('protected_roles', []):
        config['protected_roles'].remove(role.id)
        save_config()
        await ctx.send(f"❌ {role.mention} removed from protected roles")

# ============ WHITELIST COMMANDS ============
@bot.command(name='allowlink')
@commands.has_permissions(manage_messages=True)
async def allow_link(ctx, member: discord.Member):
    if member.id not in link_whitelist:
        link_whitelist.append(member.id)
        await ctx.send(f"✅ {member.mention} can post links")

@bot.command(name='blocklink')
@commands.has_permissions(manage_messages=True)
async def block_link(ctx, member: discord.Member):
    if member.id in link_whitelist:
        link_whitelist.remove(member.id)
        await ctx.send(f"❌ {member.mention} cannot post links")

@bot.command(name='whitelistrole')
@commands.has_permissions(administrator=True)
async def whitelist_role(ctx, role: discord.Role):
    if role.id not in role_whitelist:
        role_whitelist.append(role.id)
        await ctx.send(f"✅ {role.mention} whitelisted")

@bot.command(name='unwhitelistrole')
@commands.has_permissions(administrator=True)
async def unwhitelist_role(ctx, role: discord.Role):
    if role.id in role_whitelist:
        role_whitelist.remove(role.id)
        await ctx.send(f"❌ {role.mention} removed from whitelist")

@bot.command(name='whitelistuser')
@commands.has_permissions(administrator=True)
async def whitelist_user(ctx, member: discord.Member):
    if member.id not in user_whitelist:
        user_whitelist.append(member.id)
        await ctx.send(f"✅ {member.mention} whitelisted")

@bot.command(name='unwhitelistuser')
@commands.has_permissions(administrator=True)
async def unwhitelist_user(ctx, member: discord.Member):
    if member.id in user_whitelist:
        user_whitelist.remove(member.id)
        await ctx.send(f"❌ {member.mention} removed from whitelist")

@bot.command(name='whitelist')
@commands.has_permissions(administrator=True)
async def show_whitelist(ctx):
    embed = discord.Embed(title="📋 Whitelist", color=discord.Color.blue())
    
    admin_roles = [f"<@&{r}>" for r in config.get('admin_roles', [])]
    embed.add_field(name="Admin Roles", value="\n".join(admin_roles) or "None", inline=False)
    
    mod_roles = [f"<@&{r}>" for r in config.get('mod_roles', [])]
    embed.add_field(name="Mod Roles", value="\n".join(mod_roles) or "None", inline=False)
    
    protected_roles = [f"<@&{r}>" for r in config.get('protected_roles', [])]
    embed.add_field(name="Protected Roles", value="\n".join(protected_roles) or "None", inline=False)
    
    whitelisted_roles = [f"<@&{r}>" for r in role_whitelist]
    embed.add_field(name="Whitelisted Roles", value="\n".join(whitelisted_roles) or "None", inline=False)
    
    whitelisted_users = [f"<@{u}>" for u in user_whitelist]
    embed.add_field(name="Whitelisted Users", value="\n".join(whitelisted_users) or "None", inline=False)
    
    await ctx.send(embed=embed)

# ============ HELP COMMAND ============
@bot.command(name='modhelp')
async def modhelp(ctx):
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Complete bot commands list",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🔊 Voice",
        value="`!join channel_id` - Join VC (muted)\n`!leave` - Leave VC\n`!vcstatus` - Check status",
        inline=False
    )
    
    embed.add_field(
        name="💬 Chat",
        value="`!hi channel_id message` - Send message to TEXT CHANNEL\n`!say message` - Say in current channel\n`!announce channel_id message` - Announce",
        inline=False
    )
    
    if has_mod_perms(ctx):
        embed.add_field(
            name="🛡️ Moderation",
            value="`!warn @user reason` - Warn\n`!warnings @user` - View warnings\n`!mute @user time reason` - Mute\n`!unmute @user` - Unmute\n`!kick @user reason` - Kick\n`!ban @user reason` - Ban\n`!clear amount` - Clear messages",
            inline=False
        )
    
    if has_admin_perms(ctx):
        embed.add_field(
            name="⚙️ Setup",
            value="`!setlog #channel` - Log channel\n`!setmute #channel` - Mute channel\n`!setmodrole @role` - Add mod role\n`!removemodrole @role` - Remove mod role\n`!setadminrole @role` - Add admin role\n`!removeadminrole @role` - Remove admin role\n`!setprotectedrole @role` - Protect role\n`!removeprotectedrole @role` - Remove protection\n`!whitelistrole @role` - Whitelist role\n`!unwhitelistrole @role` - Remove whitelist\n`!whitelistuser @user` - Whitelist user\n`!unwhitelistuser @user` - Remove whitelist\n`!whitelist` - View whitelists",
            inline=False
        )
    
    await ctx.send(embed=embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        print("🤖 Starting bot with advanced security...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")