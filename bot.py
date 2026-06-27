# bot.py - Final Secure Version
import discord
from discord.ext import commands
import asyncio
import re
import json
import os
from datetime import datetime, timedelta

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Config
config = {}
warnings = {}
muted = {}
spam_tracker = {}
ping_tracker = {}
link_whitelist = []
role_whitelist = []
user_whitelist = []

def load_config():
    global config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {
            'log_channel': None,
            'mute_channel': None,
            'auto_mute_time': 300,
            'max_warnings': 3,
            'spam_threshold': 5,
            'spam_timeframe': 5,
            'ping_threshold': 3,
            'ping_timeframe': 10,
            'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 'benchod', 'bhak', 'bsdk']
        }

load_config()
def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

# -------- ON READY --------
@bot.event
async def on_ready():
    print(f'✅ Bot Online! {bot.user}')
    await bot.change_presence(activity=discord.Game(name="!modhelp"))

# -------- HELP --------
@bot.command(name='modhelp')
async def modhelp(ctx):
    embed = discord.Embed(title="🤖 Mod Bot Commands", color=discord.Color.blue())
    embed.add_field(name="📌 Setup", value="`!setlog #channel`\n`!setmute #channel`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`!warn @user reason`\n`!mute @user time reason`\n`!unmute @user`\n`!kick @user reason`\n`!ban @user reason`", inline=False)
    embed.add_field(name="🔗 Links", value="`!allowlink @user`\n`!blocklink @user`", inline=False)
    embed.add_field(name="👑 Whitelist", value="`!whitelistrole @role`\n`!unwhitelistrole @role`\n`!whitelistuser @user`\n`!unwhitelistuser @user`\n`!whitelist`", inline=False)
    await ctx.send(embed=embed)

# -------- SET LOG --------
@bot.command(name='setlog')
@commands.is_owner()
async def set_log(ctx, channel: discord.TextChannel):
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Log channel set to {channel.mention}')

# -------- SET MUTE --------
@bot.command(name='setmute')
@commands.is_owner()
async def set_mute(ctx, channel: discord.TextChannel):
    config['mute_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Mute channel set to {channel.mention}')

# -------- LOG FUNCTION --------
async def log_event(guild, embed):
    if config.get('log_channel'):
        channel = guild.get_channel(config['log_channel'])
        if channel:
            await channel.send(embed=embed)

# -------- CHECK WHITELIST --------
def is_whitelisted(member):
    if member.guild_permissions.administrator:
        return True
    if member.id in user_whitelist:
        return True
    for role in member.roles:
        if role.id in role_whitelist:
            return True
    return False

# -------- WARN --------
@bot.command(name='warn')
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    if member == ctx.author:
        await ctx.send("❌ Can't warn yourself!")
        return
    
    if member.id not in warnings:
        warnings[member.id] = []
    
    warnings[member.id].append({'reason': reason, 'time': str(datetime.now()), 'mod': ctx.author.name})
    
    embed = discord.Embed(title="⚠️ Warning", description=f"{member.mention} warned!", color=discord.Color.orange())
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Total Warnings", value=len(warnings[member.id]))
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)
    
    if len(warnings[member.id]) >= config.get('max_warnings', 3):
        await mute_user(member, config.get('auto_mute_time', 300), "Auto mute - max warnings")
        await ctx.send(f"🔇 {member.mention} muted ({config.get('auto_mute_time', 300)}s)")

# -------- MUTE --------
@bot.command(name='mute')
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    await mute_user(member, time, reason)
    embed = discord.Embed(title="🔇 User Muted", color=discord.Color.red())
    embed.add_field(name="Time", value=f"{time}s")
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)

async def mute_user(member, time, reason):
    muted[member.id] = {'end': datetime.now() + timedelta(seconds=time)}
    mute_role = discord.utils.get(member.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await member.guild.create_role(name="Muted")
        for channel in member.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False, add_reactions=False)
    await member.add_roles(mute_role)
    await asyncio.sleep(time)
    if member.id in muted:
        await member.remove_roles(mute_role)
        del muted[member.id]

# -------- UNMUTE --------
@bot.command(name='unmute')
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        await member.remove_roles(mute_role)
        del muted[member.id]
        await ctx.send(f"✅ {member.mention} unmuted!")
    else:
        await ctx.send(f"❌ {member.mention} not muted!")

# -------- KICK --------
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    if not is_whitelisted(ctx.author):
        await ctx.send("❌ You don't have permission!")
        return
    embed = discord.Embed(title="👢 User Kicked", color=discord.Color.red())
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    await member.kick(reason=reason)
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)

# -------- BAN --------
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    if not is_whitelisted(ctx.author):
        await ctx.send("❌ You don't have permission!")
        return
    embed = discord.Embed(title="🔨 User Banned", color=discord.Color.red())
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    await member.ban(reason=reason)
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)

# -------- SPAM DETECTION --------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Check whitelist
    if is_whitelisted(message.author):
        await bot.process_commands(message)
        return
    
    # -------- SPAM DETECTION --------
    if message.author.id not in spam_tracker:
        spam_tracker[message.author.id] = []
    
    spam_tracker[message.author.id].append(datetime.now())
    recent = [t for t in spam_tracker[message.author.id] if (datetime.now() - t).seconds < config.get('spam_timeframe', 5)]
    
    if len(recent) > config.get('spam_threshold', 5):
        await message.delete()
        embed = discord.Embed(title="🚫 Spam Detected!", description=f"{message.author.mention} Bhai spam mat kar!", color=discord.Color.red())
        await message.channel.send(embed=embed, delete_after=5)
        if len(recent) > 10:
            await mute_user(message.author, 300, "Spamming")
        spam_tracker[message.author.id] = []
    
    # -------- PING SPAM DETECTION --------
    ping_count = len(re.findall(r'<@!?&?\d+>', message.content))
    if ping_count > 0:
        if message.author.id not in ping_tracker:
            ping_tracker[message.author.id] = []
        ping_tracker[message.author.id].append(datetime.now())
        recent_pings = [t for t in ping_tracker[message.author.id] if (datetime.now() - t).seconds < config.get('ping_timeframe', 10)]
        
        if len(recent_pings) > config.get('ping_threshold', 3):
            await message.delete()
            embed = discord.Embed(title="🚫 Ping Spam Detected!", description=f"{message.author.mention} Bhai ping mat kar!", color=discord.Color.red())
            await message.channel.send(embed=embed, delete_after=5)
            if len(recent_pings) > 5:
                await mute_user(message.author, 300, "Ping spam")
            ping_tracker[message.author.id] = []
    
    # -------- BAD WORDS --------
    for word in config.get('bad_words', []):
        if word.lower() in message.content.lower():
            await message.delete()
            embed = discord.Embed(title="🚫 Bad Word!", description=f"{message.author.mention} Galat lafz mat use kar!", color=discord.Color.red())
            await message.channel.send(embed=embed, delete_after=5)
            break
    
    # -------- LINKS --------
    link_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(discord\.gg/[^\s]+)'
    if re.search(link_pattern, message.content):
        if message.author.id not in link_whitelist:
            await message.delete()
            embed = discord.Embed(title="🔗 Link Blocked!", description=f"{message.author.mention} Link mat daal! Permission le!", color=discord.Color.orange())
            await message.channel.send(embed=embed, delete_after=5)
    
    await bot.process_commands(message)

# -------- LINK WHITELIST --------
@bot.command(name='allowlink')
@commands.has_permissions(manage_messages=True)
async def allow_link(ctx, member: discord.Member):
    if member.id not in link_whitelist:
        link_whitelist.append(member.id)
        await ctx.send(f"✅ {member.mention} can now post links!")

@bot.command(name='blocklink')
@commands.has_permissions(manage_messages=True)
async def block_link(ctx, member: discord.Member):
    if member.id in link_whitelist:
        link_whitelist.remove(member.id)
        await ctx.send(f"❌ {member.mention} can no longer post links!")

# -------- ROLE WHITELIST --------
@bot.command(name='whitelistrole')
@commands.has_permissions(administrator=True)
async def whitelist_role(ctx, role: discord.Role):
    if role.id not in role_whitelist:
        role_whitelist.append(role.id)
        await ctx.send(f'✅ {role.mention} whitelist mein add ho gaya!')
        await log_event(ctx.guild, discord.Embed(
            title="📋 Role Whitelisted",
            description=f"{role.mention} whitelist mein add hua",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(f'❌ {role.mention} already whitelist mein hai!')

@bot.command(name='unwhitelistrole')
@commands.has_permissions(administrator=True)
async def unwhitelist_role(ctx, role: discord.Role):
    if role.id in role_whitelist:
        role_whitelist.remove(role.id)
        await ctx.send(f'❌ {role.mention} whitelist se remove ho gaya!')
    else:
        await ctx.send(f'❌ {role.mention} whitelist mein nahi hai!')

# -------- USER WHITELIST --------
@bot.command(name='whitelistuser')
@commands.has_permissions(administrator=True)
async def whitelist_user(ctx, member: discord.Member):
    if member.id not in user_whitelist:
        user_whitelist.append(member.id)
        await ctx.send(f'✅ {member.mention} whitelist mein add ho gaya!')
        await log_event(ctx.guild, discord.Embed(
            title="📋 User Whitelisted",
            description=f"{member.mention} whitelist mein add hua",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(f'❌ {member.mention} already whitelist mein hai!')

@bot.command(name='unwhitelistuser')
@commands.has_permissions(administrator=True)
async def unwhitelist_user(ctx, member: discord.Member):
    if member.id in user_whitelist:
        user_whitelist.remove(member.id)
        await ctx.send(f'❌ {member.mention} whitelist se remove ho gaya!')
    else:
        await ctx.send(f'❌ {member.mention} whitelist mein nahi hai!')

# -------- SHOW WHITELIST --------
@bot.command(name='whitelist')
@commands.has_permissions(administrator=True)
async def show_whitelist(ctx):
    embed = discord.Embed(title="📋 Whitelist", color=discord.Color.blue())
    
    roles = [f"<@&{role_id}>" for role_id in role_whitelist]
    users = [f"<@{user_id}>" for user_id in user_whitelist]
    
    embed.add_field(name="👑 Whitelisted Roles", value="\n".join(roles) if roles else "None", inline=False)
    embed.add_field(name="👤 Whitelisted Users", value="\n".join(users) if users else "None", inline=False)
    embed.add_field(name="🔗 Link Whitelist", value="\n".join([f"<@{uid}>" for uid in link_whitelist]) if link_whitelist else "None", inline=False)
    
    await ctx.send(embed=embed)

# -------- CHANNEL DELETE PROTECTION --------
@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if entry.user and not is_whitelisted(entry.user):
            await mute_user(entry.user, 300, "Channel delete without permission")
            embed = discord.Embed(title="🗑️ Channel Deleted!", description=f"{entry.user.mention} ne channel delete kiya!", color=discord.Color.red())
            embed.add_field(name="Channel", value=channel.name)
            embed.add_field(name="Action", value="Muted for 5 minutes")
            await log_event(channel.guild, embed)

# -------- CHANNEL CREATE PROTECTION --------
@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        if entry.user and not is_whitelisted(entry.user):
            await mute_user(entry.user, 300, "Channel create without permission")
            embed = discord.Embed(title="📢 Channel Created!", description=f"{entry.user.mention} ne channel banaya!", color=discord.Color.orange())
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Action", value="Muted for 5 minutes")
            await log_event(channel.guild, embed)

# -------- ROLE CREATE PROTECTION --------
@bot.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
        if entry.user and not is_whitelisted(entry.user):
            await mute_user(entry.user, 300, "Role create without permission")
            embed = discord.Embed(title="📋 Role Created!", description=f"{entry.user.mention} ne role banaya!", color=discord.Color.orange())
            embed.add_field(name="Role", value=role.name)
            embed.add_field(name="Action", value="Muted for 5 minutes")
            await log_event(role.guild, embed)

# -------- ROLE DELETE PROTECTION --------
@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        if entry.user and not is_whitelisted(entry.user):
            await mute_user(entry.user, 300, "Role delete without permission")
            embed = discord.Embed(title="🗑️ Role Deleted!", description=f"{entry.user.mention} ne role delete kiya!", color=discord.Color.red())
            embed.add_field(name="Role", value=role.name)
            embed.add_field(name="Action", value="Muted for 5 minutes")
            await log_event(role.guild, embed)

# -------- ROLE UPDATE PROTECTION --------
@bot.event
async def on_guild_role_update(before, after):
    async for entry in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
        if entry.user and not is_whitelisted(entry.user):
            await mute_user(entry.user, 300, "Role edit without permission")
            embed = discord.Embed(title="✏️ Role Edited!", description=f"{entry.user.mention} ne role edit kiya!", color=discord.Color.orange())
            embed.add_field(name="Role", value=after.name)
            embed.add_field(name="Action", value="Muted for 5 minutes")
            await log_event(before.guild, embed)

# -------- MEMBER ROLE ADD PROTECTION --------
@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role not in before.roles:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                    if entry.user and not is_whitelisted(entry.user):
                        await mute_user(entry.user, 300, "Role add without permission")
                        embed = discord.Embed(title="📋 Role Added!", description=f"{entry.user.mention} ne {after.mention} ko role diya!", color=discord.Color.orange())
                        embed.add_field(name="Role", value=role.mention)
                        embed.add_field(name="Action", value="Muted for 5 minutes")
                        await log_event(after.guild, embed)
                        break

# -------- WELCOME MESSAGE --------
@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        embed = discord.Embed(
            title="🙌 Welcome!",
            description=f"{member.mention} Welcome bhai!",
            color=discord.Color.green()
        )
        embed.add_field(name="👤 User", value=member.name)
        embed.add_field(name="📅 Joined", value=str(datetime.now()))
        await channel.send(embed=embed)
    
    embed = discord.Embed(title="👋 Member Joined", color=discord.Color.green())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Joined", value=str(datetime.now()))
    await log_event(member.guild, embed)

# -------- MEMBER LEAVE --------
@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="👋 Member Left", color=discord.Color.red())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Left", value=str(datetime.now()))
    await log_event(member.guild, embed)

# -------- MESSAGE LOGS --------
@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return
    embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red())
    embed.add_field(name="Author", value=message.author.mention)
    embed.add_field(name="Content", value=message.content[:1000] if message.content else "None")
    embed.add_field(name="Channel", value=message.channel.mention)
    await log_event(message.guild, embed)

@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user or before.content == after.content:
        return
    embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange())
    embed.add_field(name="Author", value=before.author.mention)
    embed.add_field(name="Before", value=before.content[:500])
    embed.add_field(name="After", value=after.content[:500])
    await log_event(before.guild, embed)

# -------- VOICE LOGS --------
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        embed = discord.Embed(title="🎤 Voice Update", color=discord.Color.blue())
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="From", value=before.channel.name if before.channel else "None")
        embed.add_field(name="To", value=after.channel.name if after.channel else "None")
        await log_event(member.guild, embed)

# -------- RUN --------
bot.run(TOKEN)
