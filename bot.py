# bot.py - Complete Discord Bot with AI + Moderation + Voice
import os
import sys
import subprocess

# ============ AUTO-INSTALL DEPENDENCIES ============
def install_packages():
    packages = [
        'discord.py',
        'requests',
        'aiohttp',
        'pynacl',
        'python-dotenv'
    ]
    
    print("🔍 Checking dependencies...")
    for package in packages:
        try:
            if package == 'discord.py':
                __import__('discord')
            elif package == 'requests':
                __import__('requests')
            elif package == 'aiohttp':
                __import__('aiohttp')
            elif package == 'pynacl':
                __import__('nacl')
            elif package == 'python-dotenv':
                __import__('dotenv')
            print(f"✅ {package} already installed")
        except ImportError:
            print(f"📦 Installing {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
                print(f"✅ {package} installed!")
            except Exception as e:
                print(f"❌ Failed to install {package}: {e}")

install_packages()

# ============ IMPORTS ============
import discord
from discord.ext import commands
import requests
import json
import asyncio
import re
import time
import random
from datetime import datetime, timedelta
import logging
from collections import defaultdict

# ============ SETUP ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# ============ TOKENS (From Environment) ============
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GH_TOKEN = os.getenv('GH_TOKEN')

if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not set!")
    print("💡 Add DISCORD_TOKEN to GitHub Secrets or .env file")
    exit(1)

if not GH_TOKEN:
    print("⚠️ GH_TOKEN not set! AI features will be disabled.")
    print("💡 Add GH_TOKEN to GitHub Secrets or .env file")

# ============ BOT INFO ============
BOT_NAME = "CAREFULLY"
CREATOR = "TurboIG"
OWNER = "TurboIG Web"
VERSION = "2.0.0"

# ============ INTENTS ============
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============ GLOBAL VARIABLES ============
config = {}
warnings = {}
muted = {}
spam_tracker = {}
voice_connections = {}
user_sessions = defaultdict(list)
_bot_ready = False
command_cooldown = defaultdict(int)

# ============ LOAD CONFIG ============
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
        'auto_mute_time': 300,
        'max_warnings': 3,
        'spam_threshold': 5,
        'spam_timeframe': 5,
        'bad_words': ['mc', 'bc', 'chutiya', 'bhosdi', 'gandu', 'madarchod', 
                     'benchod', 'bhak', 'bsdk', 'fuck', 'shit', 'asshole'],
        'mod_roles': [],
        'admin_roles': [],
        'ai_model': 'Llama-3.2-3b-instruct',
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

# ============ AI FUNCTION ============
def ask_ai(prompt, model=None, history=None):
    """Ask AI with GitHub Models"""
    if not GH_TOKEN:
        return "❌ GitHub Token not configured! Please set GH_TOKEN"
    
    if not config.get('ai_enabled', True):
        return "❌ AI features disabled by admin"
    
    model = model or config.get('ai_model', 'Llama-3.2-3b-instruct')
    
    messages = [
        {"role": "system", "content": f"""You are {BOT_NAME}, an AI assistant created by {CREATOR} for {OWNER}.
        You are helpful, friendly, and knowledgeable. Answer in clear, concise language.
        Keep responses under 2000 characters. Be respectful and professional."""}
    ]
    
    if history:
        messages.extend(history[-5:])
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        url = "https://models.inference.ai.azure.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
        
        return f"❌ API Error: {response.status_code}"
    
    except requests.Timeout:
        return "⏰ Request timeout! Please try again."
    except Exception as e:
        return f"❌ Error: {str(e)[:100]}"

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

# ============ MUTE SYSTEM ============
async def mute_user(member, time, reason):
    try:
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
║     📝 Version: {VERSION}                                   
║     🤖 AI Model: {config.get('ai_model', 'Llama-3.2-3b-instruct')}
║     🔑 GitHub Token: {"✅" if GH_TOKEN else "❌"}
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"@{BOT_NAME} | !help"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # ===== AI REPLY ON TAG =====
    if bot.user.mentioned_in(message):
        async with message.channel.typing():
            prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
            if prompt:
                response = ask_ai(prompt)
                await message.reply(f"🤖 {response}")
            else:
                await message.reply(f"👋 Hello! I'm {BOT_NAME}, your AI assistant. Ask me anything! 🤖")
        return
    
    await bot.process_commands(message)
    
    # ===== SPAM DETECTION =====
    if not is_admin(message.author) and not is_mod(message.author):
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
            return
        
        # ===== BAD WORDS FILTER =====
        for word in config.get('bad_words', []):
            if word.lower() in message.content.lower():
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} No bad words!", delete_after=5)
                await mute_user(message.author, 60, "Bad word")
                break

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!help`", delete_after=5)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission!", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing: {error.param}", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument!", delete_after=5)
    else:
        logger.error(f"Error: {error}")
        await ctx.send(f"❌ Error: {str(error)[:100]}", delete_after=5)

# ============ AI COMMANDS ============
@bot.command(name='ai')
async def ai_chat(ctx, *, message):
    """Ask AI anything!"""
    if len(message) > 1000:
        await ctx.send("❌ Message too long! Max 1000 characters.")
        return
    
    async with ctx.typing():
        response = ask_ai(message)
    
    if len(response) > 2000:
        parts = [response[i:i+1900] for i in range(0, len(response), 1900)]
        for part in parts:
            await ctx.send(f"🤖 {part}\n- By {CREATOR}")
    else:
        await ctx.send(f"🤖 {response}\n- By {CREATOR}")

@bot.command(name='chat')
async def chat_history(ctx, *, message):
    """Chat with AI (remembers context)"""
    user_id = ctx.author.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    
    user_sessions[user_id].append({"role": "user", "content": message})
    
    if len(user_sessions[user_id]) > 10:
        user_sessions[user_id] = user_sessions[user_id][-10:]
    
    async with ctx.typing():
        response = ask_ai(message, history=user_sessions[user_id])
        user_sessions[user_id].append({"role": "assistant", "content": response})
    
    await ctx.send(f"🤖 {response}\n- By {CREATOR}")

@bot.command(name='code')
async def code_help(ctx, *, instruction):
    """Generate code"""
    prompt = f"Write code for: {instruction}. Include explanation and example usage."
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"💻 {response}\n- By {CREATOR}")

@bot.command(name='explain')
async def explain_cmd(ctx, *, topic):
    """Explain any topic"""
    prompt = f"Explain {topic} in simple terms. Include key points and examples."
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"📚 {response}\n- By {CREATOR}")

@bot.command(name='translate')
async def translate_cmd(ctx, *, text):
    """Translate text to English"""
    prompt = f"Translate this to English: {text}"
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"📝 {response}\n- By {CREATOR}")

@bot.command(name='summarize')
async def summarize_cmd(ctx, *, text):
    """Summarize long text"""
    if len(text) < 50:
        await ctx.send("❌ Text too short! Give me at least 50 characters.")
        return
    
    prompt = f"Summarize this text concisely: {text}"
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"📋 {response}\n- By {CREATOR}")

@bot.command(name='write')
async def write_cmd(ctx, *, topic):
    """Write content on any topic"""
    prompt = f"Write content about: {topic}. Make it engaging and informative."
    async with ctx.typing():
        response = ask_ai(prompt)
    
    if len(response) > 2000:
        parts = [response[i:i+1900] for i in range(0, len(response), 1900)]
        for part in parts:
            await ctx.send(f"✍️ {part}\n- By {CREATOR}")
    else:
        await ctx.send(f"✍️ {response}\n- By {CREATOR}")

@bot.command(name='idea')
async def idea_cmd(ctx, *, topic):
    """Generate ideas"""
    prompt = f"Generate 5 creative ideas about: {topic}"
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"💡 {response}\n- By {CREATOR}")

@bot.command(name='debug')
async def debug_cmd(ctx, *, code):
    """Debug code"""
    prompt = f"Debug this code and explain the issue: {code}"
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"🔧 {response}\n- By {CREATOR}")

@bot.command(name='joke')
async def joke_cmd(ctx):
    """Get a joke"""
    prompt = "Tell me a funny joke."
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"😂 {response}\n- By {CREATOR}")

@bot.command(name='quote')
async def quote_cmd(ctx):
    """Get motivational quote"""
    prompt = "Give me a motivational quote."
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"💪 {response}\n- By {CREATOR}")

@bot.command(name='fact')
async def fact_cmd(ctx):
    """Get interesting fact"""
    prompt = "Give me an interesting fact."
    async with ctx.typing():
        response = ask_ai(prompt)
    await ctx.send(f"🧠 {response}\n- By {CREATOR}")

@bot.command(name='models')
async def list_models(ctx):
    """List available AI models"""
    models = [
        "Llama-3.2-3b-instruct (Default)",
        "GPT-4o-mini (Best Quality)",
        "Mistral (Fast)",
        "Phi-3 (Efficient)",
        "Gemma (Open Source)",
        "DeepSeek (Coding Expert)"
    ]
    
    embed = discord.Embed(
        title="🤖 Available AI Models",
        description=f"Current Model: **{config.get('ai_model', 'Llama-3.2-3b-instruct')}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="📋 Models", value="\n".join(models), inline=False)
    embed.add_field(name="💡 Usage", value="`!setmodel <model>` - Change model", inline=False)
    embed.set_footer(text=f"By {CREATOR} • {OWNER}")
    await ctx.send(embed=embed)

# ============ MODERATION COMMANDS ============
@bot.command(name='warn')
async def warn_cmd(ctx, member: discord.Member, *, reason="No reason"):
    if not is_mod(ctx.author):
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

@bot.command(name='mute')
async def mute_cmd(ctx, member: discord.Member, time: int = 300, *, reason="No reason"):
    if not is_mod(ctx.author):
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
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.set_footer(text=f"By {CREATOR}")
        await ctx.send(embed=embed)

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
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.set_footer(text=f"By {CREATOR}")
        await ctx.send(embed=embed)
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

# ============ ADMIN COMMANDS ============
@bot.command(name='setlog')
@commands.has_permissions(administrator=True)
async def set_log(ctx, channel: discord.TextChannel):
    config['log_channel'] = channel.id
    save_config()
    await ctx.send(f"✅ Log channel set to {channel.mention} - By {CREATOR}")

@bot.command(name='setmute')
@commands.has_permissions(administrator=True)
async def set_mute(ctx, channel: discord.TextChannel):
    config['mute_channel'] = channel.id
    save_config()
    await ctx.send(f"✅ Mute channel set to {channel.mention} - By {CREATOR}")

@bot.command(name='setwelcome')
@commands.has_permissions(administrator=True)
async def set_welcome(ctx, channel: discord.TextChannel):
    config['welcome_channel'] = channel.id
    save_config()
    await ctx.send(f"✅ Welcome channel set to {channel.mention} - By {CREATOR}")

@bot.command(name='setmodrole')
@commands.has_permissions(administrator=True)
async def set_mod_role(ctx, role: discord.Role):
    if role.id not in config.get('mod_roles', []):
        config['mod_roles'].append(role.id)
        save_config()
        await ctx.send(f"✅ {role.mention} added as mod role - By {CREATOR}")

@bot.command(name='removemodrole')
@commands.has_permissions(administrator=True)
async def remove_mod_role(ctx, role: discord.Role):
    if role.id in config.get('mod_roles', []):
        config['mod_roles'].remove(role.id)
        save_config()
        await ctx.send(f"❌ {role.mention} removed from mod roles - By {CREATOR}")

@bot.command(name='setadminrole')
@commands.has_permissions(administrator=True)
async def set_admin_role(ctx, role: discord.Role):
    if role.id not in config.get('admin_roles', []):
        config['admin_roles'].append(role.id)
        save_config()
        await ctx.send(f"✅ {role.mention} added as admin role - By {CREATOR}")

@bot.command(name='removeadminrole')
@commands.has_permissions(administrator=True)
async def remove_admin_role(ctx, role: discord.Role):
    if role.id in config.get('admin_roles', []):
        config['admin_roles'].remove(role.id)
        save_config()
        await ctx.send(f"❌ {role.mention} removed from admin roles - By {CREATOR}")

@bot.command(name='setmodel')
@commands.has_permissions(administrator=True)
async def set_ai_model(ctx, model: str):
    valid_models = [
        'Llama-3.2-3b-instruct',
        'GPT-4o-mini',
        'Mistral',
        'Phi-3-mini-4k-instruct',
        'Gemma-2-9b-it',
        'DeepSeek'
    ]
    
    if model not in valid_models:
        await ctx.send(f"❌ Invalid model! Available: {', '.join(valid_models)}")
        return
    
    config['ai_model'] = model
    save_config()
    await ctx.send(f"✅ AI model changed to: **{model}** - By {CREATOR}")

@bot.command(name='aitoggle')
@commands.has_permissions(administrator=True)
async def toggle_ai(ctx):
    config['ai_enabled'] = not config.get('ai_enabled', True)
    save_config()
    status = "✅ Enabled" if config['ai_enabled'] else "❌ Disabled"
    await ctx.send(f"AI features: **{status}** - By {CREATOR}")

# ============ VOICE COMMANDS ============
@bot.command(name='join')
async def join_vc(ctx, channel_id: int = None):
    """Bot ko VC mein join karo"""
    try:
        if not ctx.author.voice:
            await ctx.send("❌ Aap khud VC mein nahi ho!")
            return
        
        channel = bot.get_channel(channel_id) if channel_id else ctx.author.voice.channel
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ Invalid voice channel!")
            return
        
        if ctx.guild.id in voice_connections:
            await voice_connections[ctx.guild.id].disconnect()
            del voice_connections[ctx.guild.id]
        
        vc = await channel.connect()
        await vc.guild.change_voice_state(channel=channel, self_mute=True)
        voice_connections[ctx.guild.id] = vc
        
        await ctx.send(f"🔊 Joined {channel.mention} (Muted) - By {CREATOR}")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

@bot.command(name='leave')
async def leave_vc(ctx):
    """Bot ko VC se nikalo"""
    try:
        if ctx.guild.id in voice_connections:
            await voice_connections[ctx.guild.id].disconnect()
            del voice_connections[ctx.guild.id]
            await ctx.send(f"✅ Left VC - By {CREATOR}")
        else:
            await ctx.send("❌ Bot kisi VC mein nahi hai!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:200]}")

# ============ FUN COMMANDS ============
@bot.command(name='ping')
async def ping_cmd(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency}ms**",
        color=discord.Color.green()
    )
    embed.add_field(name="Bot", value=BOT_NAME)
    embed.add_field(name="Creator", value=CREATOR)
    embed.set_footer(text=f"{OWNER}")
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def stats_cmd(ctx):
    """Bot statistics"""
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=discord.Color.blue()
    )
    embed.add_field(name="🤖 Bot Name", value=BOT_NAME)
    embed.add_field(name="👤 Creator", value=CREATOR)
    embed.add_field(name="🌐 Owner", value=OWNER)
    embed.add_field(name="📝 Version", value=VERSION)
    embed.add_field(name="📊 Servers", value=len(bot.guilds))
    embed.add_field(name="👥 Users", value=sum(g.member_count for g in bot.guilds))
    embed.add_field(name="🤖 AI Model", value=config.get('ai_model', 'Llama-3.2-3b-instruct'))
    embed.add_field(name="📈 AI Status", value="✅ Enabled" if config.get('ai_enabled', True) else "❌ Disabled")
    embed.add_field(name="⚡ Latency", value=f"{round(bot.latency * 1000)}ms")
    embed.set_footer(text=f"{OWNER} • {BOT_NAME}")
    await ctx.send(embed=embed)

# ============ HELP COMMAND ============
@bot.command(name='help')
async def help_cmd(ctx):
    """Show all commands"""
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME} Commands",
        description=f"Created by {CREATOR} • {OWNER}",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🤖 AI Commands",
        value="`!ai <question>` - Ask AI\n"
              "`!chat <message>` - Chat with history\n"
              "`!code <instruction>` - Generate code\n"
              "`!explain <topic>` - Explain topic\n"
              "`!translate <text>` - Translate\n"
              "`!summarize <text>` - Summarize\n"
              "`!write <topic>` - Write content\n"
              "`!idea <topic>` - Get ideas\n"
              "`!debug <code>` - Debug code\n"
              "`!joke` - Get a joke\n"
              "`!quote` - Get quote\n"
              "`!fact` - Get fact\n"
              "`!models` - List AI models",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation",
        value="`!warn @user <reason>` - Warn user\n"
              "`!warnings @user` - View warnings\n"
              "`!mute @user <time> <reason>` - Mute user\n"
              "`!unmute @user` - Unmute user\n"
              "`!kick @user <reason>` - Kick user\n"
              "`!ban @user <reason>` - Ban user\n"
              "`!clear <amount>` - Clear messages",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin",
        value="`!setlog #channel` - Set log channel\n"
              "`!setmute #channel` - Set mute channel\n"
              "`!setwelcome #channel` - Set welcome channel\n"
              "`!setmodrole @role` - Add mod role\n"
              "`!removemodrole @role` - Remove mod role\n"
              "`!setadminrole @role` - Add admin role\n"
              "`!removeadminrole @role` - Remove admin role\n"
              "`!setmodel <model>` - Change AI model\n"
              "`!aitoggle` - Enable/Disable AI",
        inline=False
    )
    
    embed.add_field(
        name="🔊 Voice",
        value="`!join <channel_id>` - Join VC\n"
              "`!leave` - Leave VC",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Info",
        value="`!ping` - Check latency\n"
              "`!stats` - Bot statistics\n"
              "`!help` - Show this menu",
        inline=False
    )
    
    embed.set_footer(text=f"Created by {CREATOR} • Powered by GitHub Models")
    await ctx.send(embed=embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        print("🤖 Starting bot with full features...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")