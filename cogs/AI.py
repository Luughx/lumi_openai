import discord
from discord.ext import commands
import re
from urllib import parse, request
import os
#os.system("python -m pip install \"pymongo[srv]\"")
from pymongo import MongoClient
from time import sleep
import asyncio
from yt_dlp import YoutubeDL
from chat import *
import time
import creds

class AI_cog(commands.Cog):
    def __init__(self, client):
        self.client = client

        self.mongo_uri = creds.MONGODB_URI
        self.clientDB = MongoClient(self.mongo_uri, connect=False)
        self.db = self.clientDB["lumi_openai"]
        self.collectionChannels = self.db["channels_lumi"]
        self.collectionChats = self.db["chats_lumi"]
        self.resCounting = 0

        self.countTrain = 2

        self.playlistGuild = {}
        self.is_playing = False

        self.temporalListening = []
        self.initialTime = 0

    def response(self, msg, arguments):
        try:
            arguments = arguments.lower()

            resBot = []

            if re.search("en youtube", arguments):
                new = arguments.replace("en youtube", "").replace("busca", "").replace('"', "").strip()

                query_string = parse.urlencode({"search_query": new})
                html_content = request.urlopen(f"http://www.youtube.com/results?{query_string}")

                data = html_content.read().decode('utf-8')
                search_results = re.findall('\\/watch\\?v=(.{11})\"', data)

                resBot = f"{new} en youtube:\nhttps://www.youtube.com/watch?v={search_results[0]}" if len(search_results[0]) > 0 else "No encontre nada"
            else:
                findChannel = self.collectionChats.find_one({"channel": msg.channel.id})
                
                if not findChannel:
                    self.collectionChats.insert_one({"channel": msg.channel.id, "messages": [
                        {"role": "system", "content": str(open("data/lumi_personality.txt").read())}
                        ]})
                
                if self.initialTime == 0:
                    self.initialTime = time.time()

                if time.time() - self.initialTime >= 60:
                    self.initialTime = time.time()

                if self.resCounting >= 60 and time.time() - self.initialTime <= 60:
                    return "Espera un momento"

                findChannel = self.collectionChats.find_one({"channel": msg.channel.id})

                messages = findChannel["messages"]
                messages.append({"role": "user", "content": arguments})

                res = gpt3_completion(messages)

                if len(res) >= 2000:
                    resSplit = res.split(" ")
                    division = 0
                    for i in range(5):
                        if len(res) / (i+1) < 2000:
                            division = i+1
                            break

                    parts = len(res) / division
                    cacheSplit = []
                    characters = 0
                    for item in resSplit:
                        characters += len(item)
                        cacheSplit.append(item)
                        
                        if characters >= parts:
                            resBot.append(" ".join(cacheSplit))
                            cacheSplit = []
                            characters = 0
                    resBot.append(" ".join(cacheSplit))

                else:
                    resBot = [res]
                    
                self.resCounting += 1

                messages.append({"role": "assistant", "content": res})
                if len(messages) >= 20:
                    messages.pop(1)
                    messages.pop(1)

                self.collectionChats.find_one_and_update({"channel": msg.channel.id}, {"$set": {"messages": messages}})
                
            #resBot = resBot.replace("{server_owner}", f"{f'<@!{msg.guild.owner_id}>' if msg.guild else 'nadie'}")

            return resBot
        except Exception as err:
            print(err)
            return ["tuve un error", f"```{err}```"]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if str(message.channel.type) == "private":
            messageRes = await message.channel.send("Pensando...")
            res = self.response(message, message.content)
            first = True
            for msg in res:
                if first:
                    first = False
                    await messageRes.edit(content=msg)
                    continue
                await message.content.send(msg)
                sleep(0.5)
        if self.collectionChannels.find_one({"channel": message.channel.id}) and not message.content.startswith("l!") and not message.content.startswith("#"):
            resFunctions = await self.functions(message, message.content)
            if resFunctions:
                return
            messageRes = await message.channel.send("Pensando...")
            res = self.response(message, message.content)
            first = True
            for msg in res:
                if first:
                    first = False
                    await messageRes.edit(content=msg)
                    continue
                await message.content.send(msg)
                sleep(0.5)
        #await self.client.process_commands(message)

    @commands.command()
    async def channel(self, ctx, *args):
        channel = self.collectionChannels.find_one({"channel": ctx.channel.id})
        if not channel:
            self.collectionChannels.insert_one({"channel": ctx.channel.id})
            await ctx.send("Se establecio este canal")
        else:
            self.collectionChannels.find_one_and_delete({"channel": ctx.channel.id})
            await ctx.send("Se elimino este canal")

    @commands.command()
    async def chat(self, ctx, *args):
        arguments = " ".join(args)
        resFunctions = await self.functions(ctx, arguments)
        if resFunctions:
            return
        
        messageRes = await ctx.send("Pensando...")
        res = self.response(ctx, arguments)
        first = True
        for message in res:
            if first:
                first = False
                await messageRes.edit(content=message)
                continue
            await ctx.send(message)
            sleep(0.5)

async def setup(client):
    await client.add_cog(AI_cog(client))