# bot.py - Fixed Version
import discord
from discord.ext import commands
import asyncio
import re
import json
import os
from datetime import datetime, timedelta

# Token (GitHub Secrets se lega)
TOKEN = os.getenv('DISCORD_TOKEN')

# Intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Config load
config = {}
warnings = {}
muted = {}
spam_tracker = {}
link_whitelist = []

def load_config():
    global config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {
            'log_channel': None,
            'mute_channel': None,
            'auto_mute_time': 60,
            'max_warnings': 3,
            'spam_threshold': 5,
            'spam_timeframe': 5,
            'bad_words': []
        }

load_config()

def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

# -------- ON READY --------
@bot.event
async def on_ready():
    print(f'✅ Bot Online! {bot.user}')
    await bot.change_presence(activity=discord.Game(name="!modhelp | Mod Bot"))

# -------- HELP COMMAND (Renamed to !modhelp) --------
@bot.command(name='modhelp')
async def modhelp(ctx):
    embed = discord.Embed(
        title="🤖 Mod Bot Commands",
        description="Complete Moderation Bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="📌 Setup", value="`!setlog #channel` - Set log channel\n`!setmute #channel` - Set mute channel", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`!warn @user reason` - Warn user\n`!mute @user time reason` - Mute user\n`!unmute @user` - Unmute user\n`!kick @user reason` - Kick user\n`!ban @user reason` - Ban user", inline=False)
    embed.add_field(name="🔗 Links", value="`!allowlink @user` - Allow links\n`!blocklink @user` - Block links", inline=False)
    await ctx.send(embed=embed)

# -------- SET LOG (OWNER ONLY) --------
@bot.command(name='setlog')
@commands.is_owner()
async def set_log(ctx, channel: discord.TextChannel):
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Log channel set to {channel.mention}')

# -------- SET MUTE (OWNER ONLY) --------
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
        await mute_user(member, config.get('auto_mute_time', 60), "Auto mute - max warnings")
        await ctx.send(f"🔇 {member.mention} muted ({config.get('auto_mute_time', 60)}s)")

# -------- MUTE --------
@bot.command(name='mute')
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, time: int = 60, *, reason="No reason"):
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
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
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
    
    # Spam detection
    if message.author.id not in spam_tracker:
        spam_tracker[message.author.id] = []
    
    spam_tracker[message.author.id].append(datetime.now())
    recent = [t for t in spam_tracker[message.author.id] if (datetime.now() - t).seconds < config.get('spam_timeframe', 5)]
    
    if len(recent) > config.get('spam_threshold', 5):
        await message.delete()
        embed = discord.Embed(title="🚫 Spam Detected!", description=f"{message.author.mention} Don't spam!", color=discord.Color.red())
        await message.channel.send(embed=embed, delete_after=5)
        if len(recent) > 10:
            await mute_user(message.author, 120, "Spamming")
        spam_tracker[message.author.id] = []
    
    # Bad words
    for word in config.get('bad_words', []):
        if word.lower() in message.content.lower():
            await message.delete()
            embed = discord.Embed(title="🚫 Bad Word!", description=f"{message.author.mention} Watch your language!", color=discord.Color.red())
            await message.channel.send(embed=embed, delete_after=5)
            break
    
    # Links
    link_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(discord\.gg/[^\s]+)'
    if re.search(link_pattern, message.content):
        if not message.author.guild_permissions.administrator and message.author.id not in link_whitelist:
            await message.delete()
            embed = discord.Embed(title="🔗 Link Blocked!", description=f"{message.author.mention} Ask permission for links!", color=discord.Color.orange())
            await message.channel.send(embed=embed, delete_after=5)
    
    await bot.process_commands(message)

# -------- ALLOW LINK --------
@bot.command(name='allowlink')
@commands.has_permissions(manage_messages=True)
async def allow_link(ctx, member: discord.Member):
    if member.id not in link_whitelist:
        link_whitelist.append(member.id)
        await ctx.send(f"✅ {member.mention} can now post links!")

# -------- BLOCK LINK --------
@bot.command(name='blocklink')
@commands.has_permissions(manage_messages=True)
async def block_link(ctx, member: discord.Member):
    if member.id in link_whitelist:
        link_whitelist.remove(member.id)
        await ctx.send(f"❌ {member.mention} can no longer post links!")

# -------- EVENT LOGS --------
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

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        embed = discord.Embed(title="🎤 Voice Update", color=discord.Color.blue())
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="From", value=before.channel.name if before.channel else "None")
        embed.add_field(name="To", value=after.channel.name if after.channel else "None")
        await log_event(member.guild, embed)

@bot.event
async def on_member_join(member):
    embed = discord.Embed(title="👋 Member Joined", color=discord.Color.green())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Joined", value=str(datetime.now()))
    await log_event(member.guild, embed)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="👋 Member Left", color=discord.Color.red())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Left", value=str(datetime.now()))
    await log_event(member.guild, embed)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        for role in after.roles:
            if role not in before.roles:
                embed = discord.Embed(title="📋 Role Added", color=discord.Color.green())
                embed.add_field(name="User", value=after.mention)
                embed.add_field(name="Role", value=role.mention)
                await log_event(after.guild, embed)

# -------- RUN --------
bot.run(TOKEN)
