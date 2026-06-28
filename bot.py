# bot.py - Complete Working Version with VC & Chat Features
import discord
from discord.ext import commands
import asyncio
import re
import json
import os
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Get token from environment variable
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
    exit(1)

# Bot setup with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Global variables
config = {}
warnings = {}
muted = {}
spam_tracker = {}
ping_tracker = {}
link_whitelist = []
role_whitelist = []
user_whitelist = []
voice_connections = {}  # Track voice connections per guild

# ============ CONFIG MANAGEMENT ============
def load_config():
    """Load configuration from file"""
    global config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger.info("Config loaded successfully")
    except FileNotFoundError:
        logger.warning("Config file not found, creating default")
        config = {
            'log_channel': None,
            'mute_channel': None,
            'auto_mute_time': 300,
            'max_warnings': 3,
            'spam_threshold': 5,
            'spam_timeframe': 5,
            'ping_threshold': 3,
            'ping_timeframe': 10,
            'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 'benchod', 'bhak', 'bsdk', 'fuck', 'shit', 'asshole'],
            'mod_roles': [],
            'admin_roles': []
        }
        save_config()
    except json.JSONDecodeError:
        logger.error("Config file corrupted, creating new")
        config = {
            'log_channel': None,
            'mute_channel': None,
            'auto_mute_time': 300,
            'max_warnings': 3,
            'spam_threshold': 5,
            'spam_timeframe': 5,
            'ping_threshold': 3,
            'ping_timeframe': 10,
            'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 'benchod', 'bhak', 'bsdk', 'fuck', 'shit', 'asshole'],
            'mod_roles': [],
            'admin_roles': []
        }
        save_config()

def save_config():
    """Save configuration to file"""
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        logger.info("Config saved successfully")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

# Load config on startup
load_config()

# ============ PERMISSION CHECKS ============
def is_admin(member):
    """Check if member has admin permissions"""
    if not member:
        return False
    if member.guild_permissions.administrator:
        return True
    for role in member.roles:
        if role.id in config.get('admin_roles', []):
            return True
    return False

def is_mod(member):
    """Check if member has mod permissions"""
    if not member:
        return False
    if is_admin(member):
        return True
    if member.guild_permissions.manage_messages:
        return True
    for role in member.roles:
        if role.id in config.get('mod_roles', []):
            return True
    return False

def is_whitelisted(member):
    """Check if member is whitelisted"""
    if not member:
        return False
    if is_admin(member):
        return True
    if member.id in user_whitelist:
        return True
    for role in member.roles:
        if role.id in role_whitelist:
            return True
    return False

def has_mod_perms(ctx):
    """Check if command user has moderation permissions"""
    if not ctx or not ctx.author:
        return False
    return is_mod(ctx.author) or ctx.author.guild_permissions.manage_messages

def has_admin_perms(ctx):
    """Check if command user has admin permissions"""
    if not ctx or not ctx.author:
        return False
    return is_admin(ctx.author) or ctx.author.guild_permissions.administrator

# ============ LOGGING ============
async def log_event(guild, embed):
    """Send log message to configured log channel"""
    if not guild:
        return
    if config.get('log_channel'):
        channel = guild.get_channel(config['log_channel'])
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Cannot send logs to channel {config['log_channel']}")
            except Exception as e:
                logger.error(f"Error sending log: {e}")

# ============ MUTE SYSTEM ============
async def mute_user(member, time, reason="No reason"):
    """Mute a user for specified time"""
    try:
        if not member:
            return False
            
        # Don't mute admins
        if is_admin(member):
            logger.info(f"Attempted to mute admin {member.name}")
            return False
        
        # Don't mute bot owner
        if member == member.guild.owner:
            logger.info(f"Attempted to mute server owner {member.name}")
            return False
            
        muted[member.id] = {
            'end': datetime.now() + timedelta(seconds=time),
            'reason': reason
        }
        
        # Get or create mute role
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if not mute_role:
            try:
                mute_role = await member.guild.create_role(name="Muted")
                # Set permissions for all channels
                for channel in member.guild.channels:
                    try:
                        await channel.set_permissions(mute_role, 
                            send_messages=False, 
                            speak=False, 
                            add_reactions=False,
                            connect=False,
                            stream=False
                        )
                    except discord.Forbidden:
                        continue
                    except Exception as e:
                        logger.error(f"Error setting mute permissions in {channel.name}: {e}")
            except Exception as e:
                logger.error(f"Error creating mute role: {e}")
                return False
        
        # Add mute role
        try:
            await member.add_roles(mute_role, reason=f"Muted: {reason}")
        except discord.Forbidden:
            logger.error(f"Cannot add mute role to {member.name} - Missing permissions")
            return False
        except Exception as e:
            logger.error(f"Error adding mute role: {e}")
            return False
        
        # Send notification in mute channel if configured
        if config.get('mute_channel'):
            channel = member.guild.get_channel(config['mute_channel'])
            if channel:
                embed = discord.Embed(
                    title="🔇 User Muted",
                    description=f"{member.mention} has been muted",
                    color=discord.Color.red()
                )
                embed.add_field(name="Duration", value=f"{time} seconds")
                embed.add_field(name="Reason", value=reason)
                try:
                    await channel.send(embed=embed)
                except:
                    pass
        
        # Auto unmute task
        async def unmute_task():
            await asyncio.sleep(time)
            if member.id in muted:
                try:
                    await member.remove_roles(mute_role, reason="Auto unmute")
                    del muted[member.id]
                    
                    # Send unmute notification
                    if config.get('mute_channel'):
                        channel = member.guild.get_channel(config['mute_channel'])
                        if channel:
                            embed = discord.Embed(
                                title="🔊 User Unmuted",
                                description=f"{member.mention} has been unmuted automatically",
                                color=discord.Color.green()
                            )
                            try:
                                await channel.send(embed=embed)
                            except:
                                pass
                except Exception as e:
                    logger.error(f"Error in unmute task: {e}")
        
        bot.loop.create_task(unmute_task())
        return True
        
    except Exception as e:
        logger.error(f"Error muting user: {e}")
        return False

# ============ VOICE CHANNEL COMMANDS ============
@bot.command(name='join')
async def join_vc(ctx, channel_id: int):
    """Bot ko VC mein join karo (mute rahega)"""
    try:
        # Check if user is in a voice channel
        if not ctx.author.voice:
            await ctx.send("❌ Aap khud VC mein nahi ho! Pehle VC join karo.")
            return
        
        # Get the voice channel
        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("❌ Invalid channel ID! Sahi VC ID do.")
            return
        
        if not isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ Yeh voice channel nahi hai! Voice channel ID do.")
            return
        
        # Disconnect if already connected to this guild
        if ctx.guild.id in voice_connections:
            try:
                await voice_connections[ctx.guild.id].disconnect()
                del voice_connections[ctx.guild.id]
            except:
                pass
        
        # Connect to voice channel
        vc = await channel.connect()
        
        # Mute the bot (self-mute)
        await vc.guild.change_voice_state(channel=channel, self_mute=True, self_deaf=False)
        
        # Store connection
        voice_connections[ctx.guild.id] = vc
        
        embed = discord.Embed(
            title="🔊 Bot Joined Voice Channel",
            description=f"Joined {channel.mention} (🔇 Muted)",
            color=discord.Color.green()
        )
        embed.add_field(name="Channel", value=channel.name)
        embed.add_field(name="Status", value="Muted (Can listen, can't speak)")
        embed.add_field(name="Requested by", value=ctx.author.mention)
        await ctx.send(embed=embed)
        
        logger.info(f"Bot joined VC {channel.name} in {ctx.guild.name}")
        
    except discord.Forbidden:
        await ctx.send("❌ Bot ko VC join karne ki permission nahi hai! `Connect` permission do.")
    except discord.InvalidArgument:
        await ctx.send("❌ Invalid channel! Sahi VC ID do.")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")
        logger.error(f"Error in join_vc: {e}")

@bot.command(name='leave')
async def leave_vc(ctx):
    """Bot ko VC se nikalo"""
    try:
        if ctx.guild.id in voice_connections:
            vc = voice_connections[ctx.guild.id]
            if vc.is_connected():
                await vc.disconnect()
            del voice_connections[ctx.guild.id]
            
            embed = discord.Embed(
                title="🔊 Bot Left Voice Channel",
                description="Bot VC se nikal gaya!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logger.info(f"Bot left VC in {ctx.guild.name}")
        else:
            await ctx.send("❌ Bot kisi VC mein nahi hai!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='status')
async def vc_status(ctx):
    """Check bot voice status"""
    if ctx.guild.id in voice_connections:
        vc = voice_connections[ctx.guild.id]
        if vc.is_connected():
            channel = vc.channel
            embed = discord.Embed(
                title="🎤 Bot Voice Status",
                color=discord.Color.blue()
            )
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Connected", value="✅ Yes")
            embed.add_field(name="Muted", value="🔇 Yes" if vc.is_muted() else "🔊 No")
            embed.add_field(name="Members", value=len(channel.members))
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Bot disconnected but still in tracking. Use `!leave` to reset.")
            del voice_connections[ctx.guild.id]
    else:
        await ctx.send("❌ Bot kisi VC mein nahi hai!")

# ============ CHAT COMMANDS ============
@bot.command(name='hi')
async def send_hi(ctx, channel_id: int, *, message):
    """Kisi specific channel mein message bhejo"""
    try:
        # Get channel
        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("❌ Invalid channel ID! Sahi channel ID do.")
            return
        
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await ctx.send("❌ Yeh text channel nahi hai! Text channel ID do.")
            return
        
        # Check permissions
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages:
            await ctx.send("❌ Bot ko is channel mein message bhejne ki permission nahi!")
            return
        
        # Send message
        await channel.send(message)
        
        embed = discord.Embed(
            title="✅ Message Sent",
            description=f"Message sent to {channel.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Message", value=message[:500] + ("..." if len(message) > 500 else ""))
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Sent by", value=ctx.author.mention)
        await ctx.send(embed=embed)
        
        logger.info(f"Message sent to {channel.name} by {ctx.author.name}")
        
    except discord.Forbidden:
        await ctx.send("❌ Bot ko uss channel mein message bhejne ki permission nahi!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='say')
async def say_cmd(ctx, *, message):
    """Current channel mein message bhejo"""
    try:
        await ctx.send(message)
        # Delete the command message
        try:
            await ctx.message.delete()
        except:
            pass
        logger.info(f"Say command used by {ctx.author.name} in {ctx.channel.name}")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='announce')
async def announce_cmd(ctx, channel_id: int, *, message):
    """Announcement bhejo with embed"""
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            await ctx.send("❌ Invalid channel ID!")
            return
        
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Announced by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await channel.send(embed=embed)
        
        confirm_embed = discord.Embed(
            title="✅ Announcement Sent",
            description=f"Announcement sent to {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=confirm_embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'✅ Bot is online! Logged in as {bot.user}')
    print(f'📊 Connected to {len(bot.guilds)} servers')
    
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
    """Global error handler"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!modhelp` to see available commands.", delete_after=5)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param}", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided!", delete_after=5)
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ I don't have permission to do that! Please check my permissions.", delete_after=5)
    elif isinstance(error, commands.NotOwner):
        await ctx.send("❌ This command is owner only!", delete_after=5)
    else:
        logger.error(f"Unhandled error: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)[:100]}", delete_after=5)

@bot.event
async def on_voice_state_update(member, before, after):
    """Track voice state changes for bot"""
    # If bot disconnected manually
    if member.id == bot.user.id:
        if before.channel and not after.channel:
            # Bot disconnected
            if member.guild.id in voice_connections:
                try:
                    del voice_connections[member.guild.id]
                    logger.info(f"Bot disconnected from VC in {member.guild.name}")
                except:
                    pass
        
        # Check if bot got unmuted
        if before.channel and after.channel:
            if before.self_mute != after.self_mute:
                if after.self_mute == False:
                    # Bot got unmuted, mute it again
                    try:
                        vc = voice_connections.get(member.guild.id)
                        if vc and vc.is_connected():
                            await member.guild.change_voice_state(
                                channel=after.channel, 
                                self_mute=True
                            )
                            logger.info("Bot was unmuted, muted again")
                    except:
                        pass
    
    # Log voice state changes for users
    if member.id != bot.user.id:
        if before.channel != after.channel:
            embed = discord.Embed(
                title="🎤 Voice Update",
                color=discord.Color.blue()
            )
            embed.add_field(name="User", value=member.mention)
            embed.add_field(name="From", value=before.channel.name if before.channel else "Disconnected")
            embed.add_field(name="To", value=after.channel.name if after.channel else "Disconnected")
            await log_event(member.guild, embed)

# ============ HELP COMMAND ============
@bot.command(name='modhelp')
async def modhelp(ctx):
    """Show all available commands"""
    embed = discord.Embed(
        title="🤖 Mod Bot Commands",
        description="Here are all the available commands:",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Bot by: {bot.user}", icon_url=bot.user.display_avatar.url)
    
    # User commands (always visible)
    embed.add_field(
        name="📊 Information",
        value="`!serverinfo` - Server information\n`!userinfo @user` - User information",
        inline=False
    )
    
    # Voice commands (visible to all)
    embed.add_field(
        name="🔊 Voice Commands",
        value=(
            "`!join channel_id` - Bot ko VC mein join karo (mute)\n"
            "`!leave` - Bot ko VC se nikaalo\n"
            "`!status` - Bot ki VC status dekho"
        ),
        inline=False
    )
    
    # Chat commands (visible to all)
    embed.add_field(
        name="💬 Chat Commands",
        value=(
            "`!hi channel_id message` - Kisi channel mein message bhejo\n"
            "`!say message` - Current channel mein message bhejo\n"
            "`!announce channel_id message` - Announcement bhejo"
        ),
        inline=False
    )
    
    # Mod commands (visible to mods)
    if has_mod_perms(ctx) or is_admin(ctx.author):
        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "`!warn @user reason` - Warn a user\n"
                "`!warnings @user` - View user warnings\n"
                "`!mute @user time(s) reason` - Mute a user\n"
                "`!unmute @user` - Unmute a user\n"
                "`!kick @user reason` - Kick a user\n"
                "`!ban @user reason` - Ban a user\n"
                "`!clear amount` - Clear messages (max 100)"
            ),
            inline=False
        )
        embed.add_field(
            name="🔗 Link Control",
            value="`!allowlink @user` - Allow user to post links\n`!blocklink @user` - Block user from posting links",
            inline=False
        )
    
    # Admin commands (visible to admins)
    if has_admin_perms(ctx) or is_admin(ctx.author):
        embed.add_field(
            name="⚙️ Setup",
            value=(
                "`!setlog #channel` - Set log channel\n"
                "`!setmute #channel` - Set mute notification channel\n"
                "`!setmodrole @role` - Add mod role\n"
                "`!removemodrole @role` - Remove mod role\n"
                "`!setadminrole @role` - Add admin role\n"
                "`!removeadminrole @role` - Remove admin role"
            ),
            inline=False
        )
        embed.add_field(
            name="👑 Whitelist",
            value=(
                "`!whitelistrole @role` - Add role to whitelist\n"
                "`!unwhitelistrole @role` - Remove role from whitelist\n"
                "`!whitelistuser @user` - Add user to whitelist\n"
                "`!unwhitelistuser @user` - Remove user from whitelist\n"
                "`!whitelist` - Show all whitelists"
            ),
            inline=False
        )
    
    await ctx.send(embed=embed)

# ============ INFO COMMANDS ============
@bot.command(name='serverinfo')
async def server_info(ctx):
    """Show server information"""
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        description=guild.description or "No description set",
        color=discord.Color.blue()
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    # Count members by status
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    
    embed.add_field(name="👑 Owner", value=guild.owner.mention)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="👥 Total Members", value=guild.member_count)
    embed.add_field(name="🟢 Online", value=online)
    embed.add_field(name="📊 Channels", value=len(guild.channels))
    embed.add_field(name="🎭 Roles", value=len(guild.roles))
    
    if guild.premium_subscription_count:
        embed.add_field(name="🔊 Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)")
    
    embed.set_footer(text=f"Server ID: {guild.id}")
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def user_info(ctx, member: discord.Member = None):
    """Show user information"""
    member = member or ctx.author
    
    embed = discord.Embed(
        title=f"👤 {member.name}",
        color=member.color or discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    embed.add_field(name="🆔 ID", value=member.id)
    embed.add_field(name="📛 Display Name", value=member.display_name)
    embed.add_field(name="📅 Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "Unknown")
    embed.add_field(name="📅 Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="🎭 Roles", value=", ".join([role.mention for role in member.roles[1:]]) or "None")
    embed.add_field(name="🤖 Bot", value="✅ Yes" if member.bot else "❌ No")
    embed.add_field(name="👑 Admin", value="✅ Yes" if is_admin(member) else "❌ No")
    embed.add_field(name="🛡️ Mod", value="✅ Yes" if is_mod(member) else "❌ No")
    
    await ctx.send(embed=embed)

# ============ MODERATION COMMANDS ============
@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    """Clear messages in a channel (max 100)"""
    if amount < 1:
        await ctx.send("❌ Amount must be at least 1!", delete_after=5)
        return
    
    if amount > 100:
        await ctx.send("❌ Cannot delete more than 100 messages at once!", delete_after=5)
        return
    
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages!")
        await asyncio.sleep(3)
        await msg.delete()
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to delete messages!")
    except Exception as e:
        await ctx.send(f"❌ Error deleting messages: {str(e)[:100]}")

@bot.command(name='warn')
async def warn_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Warn a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to warn members!", delete_after=5)
        return
    
    if member == ctx.author:
        await ctx.send("❌ You can't warn yourself!", delete_after=5)
        return
    
    if is_admin(member):
        await ctx.send("❌ You can't warn an admin!", delete_after=5)
        return
    
    if member.bot:
        await ctx.send("❌ You can't warn a bot!", delete_after=5)
        return
    
    # Initialize warnings list if not exists
    if member.id not in warnings:
        warnings[member.id] = []
    
    # Add warning
    warnings[member.id].append({
        'reason': reason,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'mod': ctx.author.name
    })
    
    # Create embed
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"{member.mention} has been warned!",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Total Warnings", value=len(warnings[member.id]))
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)
    
    # Auto-mute if warnings exceed limit
    if len(warnings[member.id]) >= config.get('max_warnings', 3):
        if await mute_user(member, config.get('auto_mute_time', 300), "Auto mute - max warnings"):
            auto_embed = discord.Embed(
                title="🔇 Auto Mute",
                description=f"{member.mention} has been automatically muted for {config.get('auto_mute_time', 300)} seconds",
                color=discord.Color.red()
            )
            await ctx.send(embed=auto_embed)

@bot.command(name='warnings')
async def view_warnings(ctx, member: discord.Member):
    """View warnings for a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to view warnings!", delete_after=5)
        return
    
    if member.id not in warnings or not warnings[member.id]:
        await ctx.send(f"✅ {member.mention} has no warnings!")
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.name}",
        color=discord.Color.orange()
    )
    embed.add_field(
        name="Total Warnings",
        value=len(warnings[member.id]),
        inline=False
    )
    
    # Show last 10 warnings
    for i, warn in enumerate(warnings[member.id][-10:], 1):
        embed.add_field(
            name=f"Warning #{i}",
            value=f"**Reason:** {warn['reason']}\n**Time:** {warn['time']}\n**By:** {warn['mod']}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='mute')
async def mute_cmd(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    """Mute a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to mute members!", delete_after=5)
        return
    
    if is_admin(member):
        await ctx.send("❌ You cannot mute an admin!", delete_after=5)
        return
    
    if member == ctx.author:
        await ctx.send("❌ You can't mute yourself!", delete_after=5)
        return
    
    if member.bot:
        await ctx.send("❌ You can't mute a bot!", delete_after=5)
        return
    
    if time < 1:
        await ctx.send("❌ Mute time must be at least 1 second!", delete_after=5)
        return
    
    if time > 86400:  # 24 hours max
        await ctx.send("❌ Mute time cannot exceed 24 hours!", delete_after=5)
        return
    
    if await mute_user(member, time, reason):
        embed = discord.Embed(
            title="🔇 User Muted",
            color=discord.Color.red()
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Duration", value=f"{time} seconds")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send("❌ Failed to mute user! Please check my permissions.", delete_after=5)

@bot.command(name='unmute')
async def unmute_cmd(ctx, member: discord.Member):
    """Unmute a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to unmute members!", delete_after=5)
        return
    
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if mute_role:
            try:
                await member.remove_roles(mute_role, reason=f"Unmuted by {ctx.author.name}")
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to remove the mute role!", delete_after=5)
                return
            except Exception as e:
                await ctx.send(f"❌ Error unmuting: {str(e)[:100]}", delete_after=5)
                return
        
        del muted[member.id]
        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"{member.mention} has been unmuted!",
            color=discord.Color.green()
        )
        embed.add_field(name="Moderator", value=ctx.author.mention)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {member.mention} is not muted!")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Kick a member"""
    if not is_whitelisted(ctx.author):
        await ctx.send("❌ You don't have permission to kick members!", delete_after=5)
        return
    
    if is_admin(member):
        await ctx.send("❌ You cannot kick an admin!", delete_after=5)
        return
    
    if member == ctx.author:
        await ctx.send("❌ You can't kick yourself!", delete_after=5)
        return
    
    if member.bot:
        await ctx.send("❌ You can't kick a bot!", delete_after=5)
        return
    
    embed = discord.Embed(
        title="👢 User Kicked",
        color=discord.Color.red()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    try:
        await member.kick(reason=f"{reason} - By {ctx.author.name}")
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this user!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Error kicking user: {str(e)[:100]}", delete_after=5)

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Ban a member"""
    if not is_whitelisted(ctx.author):
        await ctx.send("❌ You don't have permission to ban members!", delete_after=5)
        return
    
    if is_admin(member):
        await ctx.send("❌ You cannot ban an admin!", delete_after=5)
        return
    
    if member == ctx.author:
        await ctx.send("❌ You can't ban yourself!", delete_after=5)
        return
    
    if member.bot:
        await ctx.send("❌ You can't ban a bot!", delete_after=5)
        return
    
    embed = discord.Embed(
        title="🔨 User Banned",
        color=discord.Color.red()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    try:
        await member.ban(reason=f"{reason} - By {ctx.author.name}")
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Error banning user: {str(e)[:100]}", delete_after=5)

# ============ ADMIN SETUP COMMANDS ============
@bot.command(name='setlog')
@commands.has_permissions(administrator=True)
async def set_log(ctx, channel: discord.TextChannel):
    """Set log channel"""
    config['log_channel'] = channel.id
    save_config()
    embed = discord.Embed(
        title="✅ Log Channel Set",
        description=f"Log channel set to {channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='setmute')
@commands.has_permissions(administrator=True)
async def set_mute(ctx, channel: discord.TextChannel):
    """Set mute notification channel"""
    config['mute_channel'] = channel.id
    save_config()
    embed = discord.Embed(
        title="✅ Mute Channel Set",
        description=f"Mute notification channel set to {channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='setmodrole')
@commands.has_permissions(administrator=True)
async def set_mod_role(ctx, role: discord.Role):
    """Add a mod role"""
    if role.id not in config.get('mod_roles', []):
        config['mod_roles'].append(role.id)
        save_config()
        embed = discord.Embed(
            title="✅ Mod Role Added",
            description=f"{role.mention} added as moderator role",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {role.mention} is already a mod role!")

@bot.command(name='removemodrole')
@commands.has_permissions(administrator=True)
async def remove_mod_role(ctx, role: discord.Role):
    """Remove a mod role"""
    if role.id in config.get('mod_roles', []):
        config['mod_roles'].remove(role.id)
        save_config()
        embed = discord.Embed(
            title="❌ Mod Role Removed",
            description=f"{role.mention} removed from mod roles",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {role.mention} is not a mod role!")

@bot.command(name='setadminrole')
@commands.has_permissions(administrator=True)
async def set_admin_role(ctx, role: discord.Role):
    """Add an admin role"""
    if role.id not in config.get('admin_roles', []):
        config['admin_roles'].append(role.id)
        save_config()
        embed = discord.Embed(
            title="✅ Admin Role Added",
            description=f"{role.mention} added as admin role",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {role.mention} is already an admin role!")

@bot.command(name='removeadminrole')
@commands.has_permissions(administrator=True)
async def remove_admin_role(ctx, role: discord.Role):
    """Remove an admin role"""
    if role.id in config.get('admin_roles', []):
        config['admin_roles'].remove(role.id)
        save_config()
        embed = discord.Embed(
            title="❌ Admin Role Removed",
            description=f"{role.mention} removed from admin roles",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {role.mention} is not an admin role!")

# ============ WHITELIST COMMANDS ============
@bot.command(name='allowlink')
@commands.has_permissions(manage_messages=True)
async def allow_link(ctx, member: discord.Member):
    """Allow a user to post links"""
    if member.id not in link_whitelist:
        link_whitelist.append(member.id)
        await ctx.send(f"✅ {member.mention} can now post links!")
    else:
        await ctx.send(f"❌ {member.mention} can already post links!")

@bot.command(name='blocklink')
@commands.has_permissions(manage_messages=True)
async def block_link(ctx, member: discord.Member):
    """Block a user from posting links"""
    if member.id in link_whitelist:
        link_whitelist.remove(member.id)
        await ctx.send(f"❌ {member.mention} can no longer post links!")
    else:
        await ctx.send(f"❌ {member.mention} is already blocked from posting links!")

@bot.command(name='whitelistrole')
@commands.has_permissions(administrator=True)
async def whitelist_role(ctx, role: discord.Role):
    """Add role to whitelist"""
    if role.id not in role_whitelist:
        role_whitelist.append(role.id)
        embed = discord.Embed(
            title="✅ Role Whitelisted",
            description=f"{role.mention} added to whitelist",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {role.mention} is already in whitelist!")

@bot.command(name='unwhitelistrole')
@commands.has_permissions(administrator=True)
async def unwhitelist_role(ctx, role: discord.Role):
    """Remove role from whitelist"""
    if role.id in role_whitelist:
        role_whitelist.remove(role.id)
        embed = discord.Embed(
            title="❌ Role Removed from Whitelist",
            description=f"{role.mention} removed from whitelist",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {role.mention} is not in whitelist!")

@bot.command(name='whitelistuser')
@commands.has_permissions(administrator=True)
async def whitelist_user(ctx, member: discord.Member):
    """Add user to whitelist"""
    if member.id not in user_whitelist:
        user_whitelist.append(member.id)
        embed = discord.Embed(
            title="✅ User Whitelisted",
            description=f"{member.mention} added to whitelist",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {member.mention} is already in whitelist!")

@bot.command(name='unwhitelistuser')
@commands.has_permissions(administrator=True)
async def unwhitelist_user(ctx, member: discord.Member):
    """Remove user from whitelist"""
    if member.id in user_whitelist:
        user_whitelist.remove(member.id)
        embed = discord.Embed(
            title="❌ User Removed from Whitelist",
            description=f"{member.mention} removed from whitelist",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {member.mention} is not in whitelist!")

@bot.command(name='whitelist')
@commands.has_permissions(administrator=True)
async def show_whitelist(ctx):
    """Show all whitelists"""
    embed = discord.Embed(
        title="📋 Whitelist Overview",
        color=discord.Color.blue()
    )
    
    # Admin roles
    admin_roles_list = [f"<@&{role_id}>" for role_id in config.get('admin_roles', [])]
    embed.add_field(
        name="👑 Admin Roles",
        value="\n".join(admin_roles_list) if admin_roles_list else "None",
        inline=False
    )
    
    # Mod roles
    mod_roles_list = [f"<@&{role_id}>" for role_id in config.get('mod_roles', [])]
    embed.add_field(
        name="🛡️ Mod Roles",
        value="\n".join(mod_roles_list) if mod_roles_list else "None",
        inline=False
    )
    
    # Whitelisted roles
    roles = [f"<@&{role_id}>" for role_id in role_whitelist]
    embed.add_field(
        name="👑 Whitelisted Roles",
        value="\n".join(roles) if roles else "None",
        inline=False
    )
    
    # Whitelisted users
    users = [f"<@{user_id}>" for user_id in user_whitelist]
    embed.add_field(
        name="👤 Whitelisted Users",
        value="\n".join(users) if users else "None",
        inline=False
    )
    
    # Link whitelist
    link_users = [f"<@{uid}>" for uid in link_whitelist]
    embed.add_field(
        name="🔗 Link Whitelist",
        value="\n".join(link_users) if link_users else "None",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ============ AUTOMOD ============
@bot.event
async def on_message(message):
    """Handle incoming messages"""
    # Ignore bot messages
    if message.author == bot.user:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Skip automod for admins and whitelisted users
    if is_admin(message.author):
        return
    
    if is_whitelisted(message.author):
        return
    
    # ========== SPAM DETECTION ==========
    if message.author.id not in spam_tracker:
        spam_tracker[message.author.id] = []
    
    # Clean old entries
    current_time = datetime.now()
    spam_tracker[message.author.id] = [
        t for t in spam_tracker[message.author.id] 
        if (current_time - t).seconds < config.get('spam_timeframe', 5)
    ]
    
    # Add current message
    spam_tracker[message.author.id].append(current_time)
    
    # Check spam threshold
    if len(spam_tracker[message.author.id]) > config.get('spam_threshold', 5):
        await message.delete()
        embed = discord.Embed(
            title="🚫 Spam Detected!",
            description=f"{message.author.mention} Please don't spam!",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, delete_after=5)
        
        # Auto mute for excessive spam
        if len(spam_tracker[message.author.id]) > 10:
            await mute_user(message.author, 300, "Excessive spamming")
        
        spam_tracker[message.author.id] = []
        return
    
    # ========== PING SPAM DETECTION ==========
    ping_count = len(re.findall(r'<@!?&?\d+>', message.content))
    if ping_count > 0:
        if message.author.id not in ping_tracker:
            ping_tracker[message.author.id] = []
        
        # Clean old entries
        ping_tracker[message.author.id] = [
            t for t in ping_tracker[message.author.id] 
            if (current_time - t).seconds < config.get('ping_timeframe', 10)
        ]
        
        # Add current ping
        ping_tracker[message.author.id].append(current_time)
        
        # Check ping threshold
        if len(ping_tracker[message.author.id]) > config.get('ping_threshold', 3):
            await message.delete()
            embed = discord.Embed(
                title="🚫 Ping Spam Detected!",
                description=f"{message.author.mention} Please don't spam pings!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=5)
            
            # Auto mute for excessive ping spam
            if len(ping_tracker[message.author.id]) > 5:
                await mute_user(message.author, 300, "Excessive ping spamming")
            
            ping_tracker[message.author.id] = []
            return
    
    # ========== BAD WORDS FILTER ==========
    for word in config.get('bad_words', []):
        if word.lower() in message.content.lower():
            await message.delete()
            embed = discord.Embed(
                title="🚫 Bad Word Detected!",
                description=f"{message.author.mention} Please don't use inappropriate language!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=5)
            await mute_user(message.author, 60, "Using bad words")
            break
    
    # ========== LINK FILTER ==========
    link_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(discord\.gg/[^\s]+)'
    if re.search(link_pattern, message.content, re.IGNORECASE):
        if message.author.id not in link_whitelist:
            await message.delete()
            embed = discord.Embed(
                title="🔗 Links Blocked!",
                description=f"{message.author.mention} Please don't post links without permission!",
                color=discord.Color.orange()
            )
            await message.channel.send(embed=embed, delete_after=5)

# ============ CHANNEL PROTECTION ============
@bot.event
async def on_guild_channel_delete(channel):
    """Protect against unauthorized channel deletion"""
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 300, "Channel delete without permission")
                embed = discord.Embed(
                    title="🗑️ Channel Deleted!",
                    description=f"{entry.user.mention} deleted a channel without permission!",
                    color=discord.Color.red()
                )
                embed.add_field(name="Channel", value=channel.name)
                embed.add_field(name="Action", value="Muted for 5 minutes")
                await log_event(channel.guild, embed)
                break
    except:
        pass

@bot.event
async def on_guild_channel_create(channel):
    """Protect against unauthorized channel creation"""
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 300, "Channel create without permission")
                embed = discord.Embed(
                    title="📢 Channel Created!",
                    description=f"{entry.user.mention} created a channel without permission!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Channel", value=channel.mention)
                embed.add_field(name="Action", value="Muted for 5 minutes")
                await log_event(channel.guild, embed)
                break
    except:
        pass

@bot.event
async def on_guild_role_create(role):
    """Protect against unauthorized role creation"""
    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 300, "Role create without permission")
                embed = discord.Embed(
                    title="📋 Role Created!",
                    description=f"{entry.user.mention} created a role without permission!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Role", value=role.name)
                embed.add_field(name="Action", value="Muted for 5 minutes")
                await log_event(role.guild, embed)
                break
    except:
        pass

@bot.event
async def on_guild_role_delete(role):
    """Protect against unauthorized role deletion"""
    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if entry.user and not is_admin(entry.user):
                await mute_user(entry.user, 300, "Role delete without permission")
                embed = discord.Embed(
                    title="🗑️ Role Deleted!",
                    description=f"{entry.user.mention} deleted a role without permission!",
                    color=discord.Color.red()
                )
                embed.add_field(name="Role", value=role.name)
                embed.add_field(name="Action", value="Muted for 5 minutes")
                await log_event(role.guild, embed)
                break
    except:
        pass

@bot.event
async def on_member_update(before, after):
    """Protect against unauthorized role assignments"""
    if before.roles != after.roles:
        for role in after.roles:
            if role not in before.roles:
                try:
                    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                        if entry.user and not is_admin(entry.user):
                            await mute_user(entry.user, 300, "Role add without permission")
                            embed = discord.Embed(
                                title="📋 Role Added!",
                                description=f"{entry.user.mention} added a role without permission!",
                                color=discord.Color.orange()
                            )
                            embed.add_field(name="User", value=after.mention)
                            embed.add_field(name="Role", value=role.mention)
                            embed.add_field(name="Action", value="Muted for 5 minutes")
                            await log_event(after.guild, embed)
                            break
                except:
                    pass

# ============ MEMBER EVENTS ============
@bot.event
async def on_member_join(member):
    """Welcome new members"""
    # Welcome message in system channel
    channel = member.guild.system_channel
    if channel:
        embed = discord.Embed(
            title="🙌 Welcome!",
            description=f"{member.mention} Welcome to the server!",
            color=discord.Color.green()
        )
        embed.add_field(name="👤 User", value=member.name)
        embed.add_field(name="📅 Joined", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    # Log member join
    embed = discord.Embed(
        title="👋 Member Joined",
        color=discord.Color.green()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="Joined", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
    await log_event(member.guild, embed)

@bot.event
async def on_member_remove(member):
    """Log member leave"""
    embed = discord.Embed(
        title="👋 Member Left",
        color=discord.Color.red()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Left", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
    await log_event(member.guild, embed)

# ============ MESSAGE LOGS ============
@bot.event
async def on_message_delete(message):
    """Log message deletion"""
    if message.author == bot.user:
        return
    
    embed = discord.Embed(
        title="🗑️ Message Deleted",
        color=discord.Color.red()
    )
    embed.add_field(name="Author", value=message.author.mention)
    embed.add_field(name="Content", value=message.content[:1000] if message.content else "None")
    embed.add_field(name="Channel", value=message.channel.mention)
    await log_event(message.guild, embed)

@bot.event
async def on_message_edit(before, after):
    """Log message edit"""
    if before.author == bot.user:
        return
    
    if before.content == after.content:
        return
    
    embed = discord.Embed(
        title="✏️ Message Edited",
        color=discord.Color.orange()
    )
    embed.add_field(name="Author", value=before.author.mention)
    embed.add_field(name="Channel", value=before.channel.mention)
    embed.add_field(name="Before", value=before.content[:500] if before.content else "None")
    embed.add_field(name="After", value=after.content[:500] if after.content else "None")
    await log_event(before.guild, embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        print("🤖 Starting bot...")
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Please check your DISCORD_TOKEN environment variable.")
    except discord.DiscordException as e:
        print(f"❌ Discord error: {e}")
    except Exception as e:
        print(f"❌ Error running bot: {e}")