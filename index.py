import discord
from discord.ext import commands
import os
import asyncio
import creds
from flask import Flask, jsonify, request
import threading

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="l!", intents=intents)

@client.event
async def on_ready():
    #await client.change_presence(status=discord.Status.online, activity=discord.Game(name="Lughx"))
    print(f"i'm ready {client.user}")

async def load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await client.load_extension(f"cogs.{filename[:-3]}")

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "message": "uwu"
    })

async def main():
    await load()
    thread1 = threading.Thread(target= lambda: app.run(port=8080, host="0.0.0.0"))
    print("loading server")
    thread1.start()
    print("loading discord")
    await client.start(creds.DISCORD_TOKEN)
    
asyncio.run(main())