# bot.py - Enhanced Secure Version
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

TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
config = {}
warnings = {}
muted = {}
spam_tracker = {}
ping_tracker = {}
link_whitelist = []
role_whitelist = []
user_whitelist = []
mod_roles = []  # Roles that have mod permissions
admin_roles = []  # Roles that have admin permissions

# ============ CONFIG MANAGEMENT ============
def load_config():
    global config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {
            'log_channel': None,
            'mute_channel': None,
            'auto_mute_time': 300,
            'max_warnings': 3,
            'spam_threshold': 5,
            'spam_timeframe': 5,
            'ping_threshold': 3,
            'ping_timeframe': 10,
            'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 'benchod', 'bhak', 'bsdk', 'fuck', 'shit'],
            'mod_roles': [],
            'admin_roles': []
        }
        save_config()

def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

load_config()

# ============ PERMISSION CHECKS ============
def is_admin(member):
    """Check if member has admin permissions"""
    if member.guild_permissions.administrator:
        return True
    for role in member.roles:
        if role.id in config.get('admin_roles', []):
            return True
    return False

def is_mod(member):
    """Check if member has mod permissions"""
    if is_admin(member):
        return True
    for role in member.roles:
        if role.id in config.get('mod_roles', []):
            return True
    return False

def is_whitelisted(member):
    """Check if member is whitelisted"""
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
    return is_mod(ctx.author) or ctx.author.guild_permissions.manage_messages

def has_admin_perms(ctx):
    """Check if command user has admin permissions"""
    return is_admin(ctx.author) or ctx.author.guild_permissions.administrator

# ============ LOGGING ============
async def log_event(guild, embed):
    if config.get('log_channel'):
        channel = guild.get_channel(config['log_channel'])
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Cannot send logs to channel {config['log_channel']}")

# ============ MUTE SYSTEM ============
async def mute_user(member, time, reason="No reason"):
    """Mute a user for specified time"""
    try:
        # Don't mute admins/mod roles
        if is_admin(member):
            return False
            
        muted[member.id] = {'end': datetime.now() + timedelta(seconds=time)}
        
        # Get or create mute role
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await member.guild.create_role(name="Muted")
            # Set permissions for all channels
            for channel in member.guild.channels:
                try:
                    await channel.set_permissions(mute_role, 
                        send_messages=False, 
                        speak=False, 
                        add_reactions=False,
                        connect=False
                    )
                except discord.Forbidden:
                    continue
        
        await member.add_roles(mute_role)
        
        # Auto unmute
        async def unmute_task():
            await asyncio.sleep(time)
            if member.id in muted:
                try:
                    await member.remove_roles(mute_role)
                    del muted[member.id]
                    # Notify in mute channel
                    if config.get('mute_channel'):
                        channel = member.guild.get_channel(config['mute_channel'])
                        if channel:
                            embed = discord.Embed(
                                title="🔊 Unmuted",
                                description=f"{member.mention} has been unmuted automatically",
                                color=discord.Color.green()
                            )
                            await channel.send(embed=embed)
                except discord.HTTPException:
                    pass
        
        bot.loop.create_task(unmute_task())
        return True
        
    except discord.Forbidden:
        logger.error(f"Cannot mute {member.name} - Missing permissions")
        return False

# ============ BOT EVENTS ============
@bot.event
async def on_ready():
    print(f'✅ Bot Online! {bot.user}')
    await bot.change_presence(activity=discord.Game(name="!modhelp"))
    logger.info(f'Bot is ready! Logged in as {bot.user}')

@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.MissingRole):
        await ctx.send("❌ You don't have the required role!")
    elif isinstance(error, commands.MissingAnyRole):
        await ctx.send("❌ You don't have any of the required roles!")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!modhelp` to see available commands.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ I don't have permission to do that!")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)[:100]}")

# ============ HELP COMMAND ============
@bot.command(name='modhelp')
async def modhelp(ctx):
    """Show all available commands"""
    embed = discord.Embed(title="🤖 Mod Bot Commands", color=discord.Color.blue())
    embed.set_footer(text="Bot by: " + str(bot.user))
    
    # Only show permissions sections based on user role
    if has_mod_perms(ctx) or is_admin(ctx.author):
        embed.add_field(
            name="🛡️ Moderation", 
            value="`!warn @user reason`\n`!mute @user time(s) reason`\n`!unmute @user`\n`!kick @user reason`\n`!ban @user reason`\n`!clear amount`",
            inline=False
        )
    
    if has_admin_perms(ctx) or is_admin(ctx.author):
        embed.add_field(
            name="⚙️ Setup", 
            value="`!setlog #channel`\n`!setmute #channel`\n`!setmodrole @role`\n`!setadminrole @role`\n`!removemodrole @role`\n`!removeadminrole @role`",
            inline=False
        )
        embed.add_field(
            name="👑 Whitelist", 
            value="`!whitelistrole @role`\n`!unwhitelistrole @role`\n`!whitelistuser @user`\n`!unwhitelistuser @user`\n`!whitelist`\n`!allowlink @user`\n`!blocklink @user`",
            inline=False
        )
    
    embed.add_field(
        name="📊 Info", 
        value="`!warnings @user`\n`!serverinfo`\n`!userinfo @user`",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ============ MODERATION COMMANDS ============
@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    """Clear messages in a channel"""
    if amount < 1 or amount > 100:
        await ctx.send("❌ Amount must be between 1 and 100!")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages!")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name='warn')
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    """Warn a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to warn members!")
        return
    
    if member == ctx.author:
        await ctx.send("❌ Can't warn yourself!")
        return
    
    if is_admin(member):
        await ctx.send("❌ Can't warn an admin!")
        return
    
    if member.id not in warnings:
        warnings[member.id] = []
    
    warnings[member.id].append({
        'reason': reason, 
        'time': str(datetime.now()), 
        'mod': ctx.author.name
    })
    
    embed = discord.Embed(
        title="⚠️ Warning", 
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
            await ctx.send(f"🔇 {member.mention} has been automatically muted for {config.get('auto_mute_time', 300)}s")

@bot.command(name='warnings')
async def view_warnings(ctx, member: discord.Member):
    """View warnings for a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to view warnings!")
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
    
    for i, warn in enumerate(warnings[member.id][:10], 1):
        embed.add_field(
            name=f"Warning #{i}",
            value=f"Reason: {warn['reason']}\nTime: {warn['time']}\nBy: {warn['mod']}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='mute')
async def mute_cmd(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    """Mute a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to mute members!")
        return
    
    if is_admin(member):
        await ctx.send("❌ Cannot mute an admin!")
        return
    
    if await mute_user(member, time, reason):
        embed = discord.Embed(
            title="🔇 User Muted", 
            color=discord.Color.red()
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Time", value=f"{time}s")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send("❌ Failed to mute user! Check my permissions.")

@bot.command(name='unmute')
async def unmute_cmd(ctx, member: discord.Member):
    """Unmute a member"""
    if not has_mod_perms(ctx):
        await ctx.send("❌ You don't have permission to unmute members!")
        return
    
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        if mute_role:
            await member.remove_roles(mute_role)
        del muted[member.id]
        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"{member.mention} has been unmuted!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    else:
        await ctx.send(f"❌ {member.mention} is not muted!")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Kick a member"""
    if not is_whitelisted(ctx.author):
        await ctx.send("❌ You don't have permission to kick members!")
        return
    
    if is_admin(member):
        await ctx.send("❌ Cannot kick an admin!")
        return
    
    embed = discord.Embed(
        title="👢 User Kicked", 
        color=discord.Color.red()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    try:
        await member.kick(reason=reason)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this user!")

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Ban a member"""
    if not is_whitelisted(ctx.author):
        await ctx.send("❌ You don't have permission to ban members!")
        return
    
    if is_admin(member):
        await ctx.send("❌ Cannot ban an admin!")
        return
    
    embed = discord.Embed(
        title="🔨 User Banned", 
        color=discord.Color.red()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    try:
        await member.ban(reason=reason)
        await ctx.send(embed=embed)
        await log_event(ctx.guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user!")

# ============ ADMIN SETUP COMMANDS ============
@bot.command(name='setlog')
@commands.has_permissions(administrator=True)
async def set_log(ctx, channel: discord.TextChannel):
    """Set log channel"""
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Log channel set to {channel.mention}')

@bot.command(name='setmute')
@commands.has_permissions(administrator=True)
async def set_mute(ctx, channel: discord.TextChannel):
    """Set mute notification channel"""
    config['mute_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Mute channel set to {channel.mention}')

@bot.command(name='setmodrole')
@commands.has_permissions(administrator=True)
async def set_mod_role(ctx, role: discord.Role):
    """Add a mod role"""
    if role.id not in config.get('mod_roles', []):
        config['mod_roles'].append(role.id)
        save_config()
        await ctx.send(f'✅ {role.mention} added as mod role!')
        await log_event(ctx.guild, discord.Embed(
            title="📋 Mod Role Added",
            description=f"{role.mention} added as moderator role",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(f'❌ {role.mention} is already a mod role!')

@bot.command(name='removemodrole')
@commands.has_permissions(administrator=True)
async def remove_mod_role(ctx, role: discord.Role):
    """Remove a mod role"""
    if role.id in config.get('mod_roles', []):
        config['mod_roles'].remove(role.id)
        save_config()
        await ctx.send(f'❌ {role.mention} removed from mod roles!')
    else:
        await ctx.send(f'❌ {role.mention} is not a mod role!')

@bot.command(name='setadminrole')
@commands.has_permissions(administrator=True)
async def set_admin_role(ctx, role: discord.Role):
    """Add an admin role"""
    if role.id not in config.get('admin_roles', []):
        config['admin_roles'].append(role.id)
        save_config()
        await ctx.send(f'✅ {role.mention} added as admin role!')
        await log_event(ctx.guild, discord.Embed(
            title="📋 Admin Role Added",
            description=f"{role.mention} added as admin role",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(f'❌ {role.mention} is already an admin role!')

@bot.command(name='removeadminrole')
@commands.has_permissions(administrator=True)
async def remove_admin_role(ctx, role: discord.Role):
    """Remove an admin role"""
    if role.id in config.get('admin_roles', []):
        config['admin_roles'].remove(role.id)
        save_config()
        await ctx.send(f'❌ {role.mention} removed from admin roles!')
    else:
        await ctx.send(f'❌ {role.mention} is not an admin role!')

# ============ WHITELIST COMMANDS ============
@bot.command(name='allowlink')
@commands.has_permissions(manage_messages=True)
async def allow_link(ctx, member: discord.Member):
    """Allow a user to post links"""
    if member.id not in link_whitelist:
        link_whitelist.append(member.id)
        await ctx.send(f"✅ {member.mention} can now post links!")

@bot.command(name='blocklink')
@commands.has_permissions(manage_messages=True)
async def block_link(ctx, member: discord.Member):
    """Block a user from posting links"""
    if member.id in link_whitelist:
        link_whitelist.remove(member.id)
        await ctx.send(f"❌ {member.mention} can no longer post links!")

@bot.command(name='whitelistrole')
@commands.has_permissions(administrator=True)
async def whitelist_role(ctx, role: discord.Role):
    """Add role to whitelist"""
    if role.id not in role_whitelist:
        role_whitelist.append(role.id)
        await ctx.send(f'✅ {role.mention} added to whitelist!')
        await log_event(ctx.guild, discord.Embed(
            title="📋 Role Whitelisted",
            description=f"{role.mention} added to whitelist",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(f'❌ {role.mention} already in whitelist!')

@bot.command(name='unwhitelistrole')
@commands.has_permissions(administrator=True)
async def unwhitelist_role(ctx, role: discord.Role):
    """Remove role from whitelist"""
    if role.id in role_whitelist:
        role_whitelist.remove(role.id)
        await ctx.send(f'❌ {role.mention} removed from whitelist!')
    else:
        await ctx.send(f'❌ {role.mention} not in whitelist!')

@bot.command(name='whitelistuser')
@commands.has_permissions(administrator=True)
async def whitelist_user(ctx, member: discord.Member):
    """Add user to whitelist"""
    if member.id not in user_whitelist:
        user_whitelist.append(member.id)
        await ctx.send(f'✅ {member.mention} added to whitelist!')
        await log_event(ctx.guild, discord.Embed(
            title="📋 User Whitelisted",
            description=f"{member.mention} added to whitelist",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(f'❌ {member.mention} already in whitelist!')

@bot.command(name='unwhitelistuser')
@commands.has_permissions(administrator=True)
async def unwhitelist_user(ctx, member: discord.Member):
    """Remove user from whitelist"""
    if member.id in user_whitelist:
        user_whitelist.remove(member.id)
        await ctx.send(f'❌ {member.mention} removed from whitelist!')
    else:
        await ctx.send(f'❌ {member.mention} not in whitelist!')

@bot.command(name='whitelist')
@commands.has_permissions(administrator=True)
async def show_whitelist(ctx):
    """Show all whitelists"""
    embed = discord.Embed(title="📋 Whitelist", color=discord.Color.blue())
    
    roles = [f"<@&{role_id}>" for role_id in role_whitelist]
    users = [f"<@{user_id}>" for user_id in user_whitelist]
    link_users = [f"<@{uid}>" for uid in link_whitelist]
    mod_roles_list = [f"<@&{role_id}>" for role_id in config.get('mod_roles', [])]
    admin_roles_list = [f"<@&{role_id}>" for role_id in config.get('admin_roles', [])]
    
    embed.add_field(name="👑 Admin Roles", value="\n".join(admin_roles_list) if admin_roles_list else "None", inline=False)
    embed.add_field(name="🛡️ Mod Roles", value="\n".join(mod_roles_list) if mod_roles_list else "None", inline=False)
    embed.add_field(name="👑 Whitelisted Roles", value="\n".join(roles) if roles else "None", inline=False)
    embed.add_field(name="👤 Whitelisted Users", value="\n".join(users) if users else "None", inline=False)
    embed.add_field(name="🔗 Link Whitelist", value="\n".join(link_users) if link_users else "None", inline=False)
    
    await ctx.send(embed=embed)

# ============ INFO COMMANDS ============
@bot.command(name='serverinfo')
async def server_info(ctx):
    """Show server information"""
    guild = ctx.guild
    embed = discord.Embed(
        title=guild.name,
        description=guild.description or "No description",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👑 Owner", value=guild.owner.mention)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"))
    embed.add_field(name="👥 Members", value=guild.member_count)
    embed.add_field(name="📊 Channels", value=len(guild.channels))
    embed.add_field(name="🎭 Roles", value=len(guild.roles))
    embed.add_field(name="🔊 Boosts", value=guild.premium_subscription_count or 0)
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def user_info(ctx, member: discord.Member = None):
    """Show user information"""
    member = member or ctx.author
    embed = discord.Embed(
        title=member.name,
        color=member.color or discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 ID", value=member.id)
    embed.add_field(name="📅 Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "Unknown")
    embed.add_field(name="📅 Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="🎭 Roles", value=", ".join([role.mention for role in member.roles[1:]]) or "None")
    embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No")
    embed.add_field(name="👑 Admin", value="Yes" if is_admin(member) else "No")
    embed.add_field(name="🛡️ Mod", value="Yes" if is_mod(member) else "No")
    await ctx.send(embed=embed)

# ============ AUTOMOD ============
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Skip checks for admins
    if is_admin(message.author):
        return
    
    # Check whitelist for automod
    if is_whitelisted(message.author):
        return
    
    # -------- SPAM DETECTION --------
    if message.author.id not in spam_tracker:
        spam_tracker[message.author.id] = []
    
    spam_tracker[message.author.id].append(datetime.now())
    spam_tracker[message.author.id] = [
        t for t in spam_tracker[message.author.id] 
        if (datetime.now() - t).seconds < config.get('spam_timeframe', 5)
    ]
    
    if len(spam_tracker[message.author.id]) > config.get('spam_threshold', 5):
        await message.delete()
        embed = discord.Embed(
            title="🚫 Spam Detected!",
            description=f"{message.author.mention} Please don't spam!",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, delete_after=5)
        
        if len(spam_tracker[message.author.id]) > 10:
            await mute_user(message.author, 300, "Spamming")
        spam_tracker[message.author.id] = []
        return
    
    # -------- PING SPAM DETECTION --------
    ping_count = len(re.findall(r'<@!?&?\d+>', message.content))
    if ping_count > 0:
        if message.author.id not in ping_tracker:
            ping_tracker[message.author.id] = []
        ping_tracker[message.author.id].append(datetime.now())
        ping_tracker[message.author.id] = [
            t for t in ping_tracker[message.author.id] 
            if (datetime.now() - t).seconds < config.get('ping_timeframe', 10)
        ]
        
        if len(ping_tracker[message.author.id]) > config.get('ping_threshold', 3):
            await message.delete()
            embed = discord.Embed(
                title="🚫 Ping Spam Detected!",
                description=f"{message.author.mention} Please don't spam pings!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=5)
            
            if len(ping_tracker[message.author.id]) > 5:
                await mute_user(message.author, 300, "Ping spam")
            ping_tracker[message.author.id] = []
            return
    
    # -------- BAD WORDS --------
    for word in config.get('bad_words', []):
        if word.lower() in message.content.lower():
            await message.delete()
            embed = discord.Embed(
                title="🚫 Bad Word Detected!",
                description=f"{message.author.mention} Please don't use bad words!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=5)
            await mute_user(message.author, 60, "Using bad words")
            break
    
    # -------- LINKS --------
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

@bot.event
async def on_guild_channel_create(channel):
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

@bot.event
async def on_guild_role_create(role):
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

@bot.event
async def on_guild_role_delete(role):
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

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role not in before.roles:
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

# ============ MEMBER EVENTS ============
@bot.event
async def on_member_join(member):
    # Welcome message
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
    
    # Log
    embed = discord.Embed(
        title="👋 Member Joined",
        color=discord.Color.green()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Joined", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
    await log_event(member.guild, embed)

@bot.event
async def on_member_remove(member):
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
    if before.author == bot.user or before.content == after.content:
        return
    embed = discord.Embed(
        title="✏️ Message Edited",
        color=discord.Color.orange()
    )
    embed.add_field(name="Author", value=before.author.mention)
    embed.add_field(name="Before", value=before.content[:500])
    embed.add_field(name="After", value=after.content[:500])
    await log_event(before.guild, embed)

# ============ VOICE LOGS ============
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        embed = discord.Embed(
            title="🎤 Voice Update",
            color=discord.Color.blue()
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="From", value=before.channel.name if before.channel else "Disconnected")
        embed.add_field(name="To", value=after.channel.name if after.channel else "Disconnected")
        await log_event(member.guild, embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Please check your DISCORD_TOKEN environment variable.")
    except Exception as e:
        print(f"❌ Error running bot
