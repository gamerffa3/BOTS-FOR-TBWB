# bot.py - Complete Moderation Bot
import discord
from discord.ext import commands
import asyncio
import re
from datetime import datetime, timedelta
import json
import os

# Token (GitHub Secrets se lega)
TOKEN = os.getenv('DISCORD_TOKEN')

# Intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Data storage
config = {}
warnings = {}
muted = {}
spam_tracker = {}

# -------- ON READY --------
@bot.event
async def on_ready():
    print(f'✅ Bot Online! {bot.user}')
    await bot.change_presence(activity=discord.Game(name="!help | Mod Bot"))
    
    # Load config
    global config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {}

# -------- HELP COMMAND --------
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Mod Bot Commands",
        description="Complete Moderation Bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="📌 Setup", value="`!setlog #channel` - Set log channel\n`!setmute #channel` - Set mute channel", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`!warn @user reason` - Warn user\n`!mute @user time reason` - Mute user\n`!unmute @user` - Unmute user\n`!kick @user reason` - Kick user\n`!ban @user reason` - Ban user", inline=False)
    embed.add_field(name="🔗 Link Moderation", value="`!allowlink @user` - Allow user to post links\n`!blocklink @user` - Block user from links", inline=False)
    embed.add_field(name="⚙️ Admin", value="`!addadmin @user` - Add admin\n`!removeadmin @user` - Remove admin", inline=False)
    await ctx.send(embed=embed)

# -------- SET LOG CHANNEL (Owner Only) --------
@bot.command(name='setlog')
@commands.is_owner()
async def set_log(ctx, channel: discord.TextChannel):
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Log channel set to {channel.mention}')

# -------- SET MUTE CHANNEL (Owner Only) --------
@bot.command(name='setmute')
@commands.is_owner()
async def set_mute(ctx, channel: discord.TextChannel):
    config['mute_channel'] = channel.id
    save_config()
    await ctx.send(f'✅ Mute channel set to {channel.mention}')

# -------- SAVE CONFIG --------
def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f)

# -------- LOG FUNCTION --------
async def log_event(guild, embed):
    if 'log_channel' in config:
        channel = guild.get_channel(config['log_channel'])
        if channel:
            await channel.send(embed=embed)

# -------- WARN COMMAND --------
@bot.command(name='warn')
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    if member == ctx.author:
        await ctx.send("❌ You can't warn yourself!")
        return
    
    if member.guild_permissions.administrator:
        await ctx.send("❌ Can't warn an admin!")
        return
    
    if member.id not in warnings:
        warnings[member.id] = []
    
    warnings[member.id].append({
        'reason': reason,
        'time': datetime.now().isoformat(),
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
    
    # Check warning count
    if len(warnings[member.id]) >= 3:
        await mute_user(member, 60, "3 warnings - auto mute")
        await ctx.send(f"🔇 {member.mention} muted for 60 seconds (3 warnings)")

# -------- MUTE COMMAND --------
@bot.command(name='mute')
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, time: int = 60, *, reason="No reason"):
    await mute_user(member, time, reason)
    
    embed = discord.Embed(
        title="🔇 User Muted",
        description=f"{member.mention} has been muted!",
        color=discord.Color.red()
    )
    embed.add_field(name="Time", value=f"{time} seconds")
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)

async def mute_user(member, time, reason):
    muted[member.id] = {
        'time': time,
        'reason': reason,
        'end': datetime.now() + timedelta(seconds=time)
    }
    
    # Add mute role
    mute_role = discord.utils.get(member.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await member.guild.create_role(name="Muted")
        for channel in member.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    
    await member.add_roles(mute_role)
    
    # Auto unmute after time
    await asyncio.sleep(time)
    if member.id in muted:
        await member.remove_roles(mute_role)
        del muted[member.id]

# -------- UNMUTE COMMAND --------
@bot.command(name='unmute')
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    if member.id in muted:
        mute_role = discord.utils.get(member.guild.roles, name="Muted")
        await member.remove_roles(mute_role)
        del muted[member.id]
        await ctx.send(f"✅ {member.mention} unmuted!")
    else:
        await ctx.send(f"❌ {member.mention} is not muted!")

# -------- KICK COMMAND --------
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    if member == ctx.author:
        await ctx.send("❌ You can't kick yourself!")
        return
    
    embed = discord.Embed(
        title="👢 User Kicked",
        description=f"{member.mention} has been kicked!",
        color=discord.Color.red()
    )
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    await member.kick(reason=reason)
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)

# -------- BAN COMMAND --------
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    if member == ctx.author:
        await ctx.send("❌ You can't ban yourself!")
        return
    
    embed = discord.Embed(
        title="🔨 User Banned",
        description=f"{member.mention} has been banned!",
        color=discord.Color.red()
    )
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=ctx.author.mention)
    
    await member.ban(reason=reason)
    await ctx.send(embed=embed)
    await log_event(ctx.guild, embed)

# -------- LINK DETECTION --------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Check for links
    link_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(discord\.gg/[^\s]+)'
    links = re.findall(link_pattern, message.content)
    
    if links:
        # Check if user is allowed to post links
        if not is_allowed_links(message.author):
            await message.delete()
            embed = discord.Embed(
                title="🔗 Link Blocked!",
                description=f"{message.author.mention} You need permission to post links!",
                color=discord.Color.orange()
            )
            await message.channel.send(embed=embed, delete_after=5)
            await warn_user(message.author, "Posted link without permission")
    
    await bot.process_commands(message)

def is_allowed_links(user):
    # Check if user is admin/mod/owner
    if user.guild_permissions.administrator or user.guild_permissions.manage_messages:
        return True
    # Check whitelist
    return False

async def warn_user(user, reason):
    if user.id not in warnings:
        warnings[user.id] = []
    
    warnings[user.id].append({
        'reason': reason,
        'time': datetime.now().isoformat(),
        'mod': 'AutoMod'
    })
    
    if len(warnings[user.id]) >= 3:
        await mute_user(user, 60, "Auto mute - multiple violations")

# -------- SPAM DETECTION --------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Spam detection
    if message.author.id not in spam_tracker:
        spam_tracker[message.author.id] = []
    
    spam_tracker[message.author.id].append(datetime.now())
    
    # Check last 5 messages in 5 seconds
    recent = [t for t in spam_tracker[message.author.id] 
              if (datetime.now() - t).seconds < 5]
    
    if len(recent) > 5:
        await message.delete()
        embed = discord.Embed(
            title="🚫 Spam Detected!",
            description=f"{message.author.mention} Please don't spam!",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, delete_after=5)
        
        if len(recent) > 10:
            await mute_user(message.author, 120, "Spamming")
        
        spam_tracker[message.author.id] = []
    
    await bot.process_commands(message)

# -------- ROLE MANAGEMENT --------
@bot.event
async def on_member_update(before, after):
    # Check if roles were added/removed
    if before.roles != after.roles:
        for role in after.roles:
            if role not in before.roles:
                # Someone got a role
                embed = discord.Embed(
                    title="📋 Role Added",
                    description=f"{after.mention} got role {role.mention}",
                    color=discord.Color.green()
                )
                embed.add_field(name="Moderator", value="Auto Log")
                await log_event(after.guild, embed)

# -------- CHANNEL CREATE/DELETE --------
@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(
        title="📢 Channel Created",
        description=f"Channel: {channel.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="Type", value=str(channel.type))
    await log_event(channel.guild, embed)

@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(
        title="🗑️ Channel Deleted",
        description=f"Channel: {channel.name}",
        color=discord.Color.red()
    )
    embed.add_field(name="Type", value=str(channel.type))
    await log_event(channel.guild, embed)

# -------- VOICE CHANNEL LOGS --------
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        embed = discord.Embed(
            title="🎤 Voice Channel Update",
            description=f"{member.mention} moved channels",
            color=discord.Color.blue()
        )
        embed.add_field(name="From", value=before.channel.name if before.channel else "None")
        embed.add_field(name="To", value=after.channel.name if after.channel else "None")
        await log_event(member.guild, embed)

# -------- MESSAGE EDIT LOG --------
@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return
    
    if before.content != after.content:
        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"Author: {before.author.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Before", value=before.content[:1000], inline=False)
        embed.add_field(name="After", value=after.content[:1000], inline=False)
        embed.add_field(name="Channel", value=before.channel.mention)
        await log_event(before.guild, embed)

# -------- MESSAGE DELETE LOG --------
@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return
    
    embed = discord.Embed(
        title="🗑️ Message Deleted",
        description=f"Author: {message.author.mention}",
        color=discord.Color.red()
    )
    embed.add_field(name="Content", value=message.content[:1000] if message.content else "None", inline=False)
    embed.add_field(name="Channel", value=message.channel.mention)
    await log_event(message.guild, embed)

# -------- AUTO-MOD: BAD WORDS --------
BAD_WORDS = ['badword1', 'badword2', 'badword3']  # Add your bad words

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Check for bad words
    for word in BAD_WORDS:
        if word.lower() in message.content.lower():
            await message.delete()
            embed = discord.Embed(
                title="🚫 Bad Word Detected!",
                description=f"{message.author.mention} Please use appropriate language!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=5)
            await warn_user(message.author, f"Used bad word: {word}")
            break
    
    await bot.process_commands(message)

# -------- RUN BOT --------
bot.run(TOKEN)
