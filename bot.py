# bot.py - Simple Working Bot
import discord
import os

# Token GitHub Secrets se le rahe hain (Secure!)
TOKEN = os.getenv('DISCORD_TOKEN')

class MyBot(discord.Client):
    async def on_ready(self):
        print(f"Bot Online! {self.user}")
    
    async def on_message(self, message):
        if message.author == self.user:
            return
        
        # Simple commands
        if message.content == "!ping":
            await message.channel.send("Pong!")
        
        if message.content == "!hello":
            await message.channel.send(f"Hello {message.author.name}!")

# Run
client = MyBot()
client.run(TOKEN)
