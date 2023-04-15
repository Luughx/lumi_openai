import discord
from discord.ext import commands
import re
from urllib import parse, request
from pymongo import MongoClient
from time import sleep
import os
import asyncio
from yt_dlp import YoutubeDL
from chat import *
import time

class AI_cog(commands.Cog):
    def __init__(self, client):
        self.client = client

        self.mongo_uri = "mongodb://localhost:27017"
        self.clientDB = MongoClient(self.mongo_uri)
        self.db = self.clientDB["lumi_openai"]
        self.collectionChannels = self.db["channels_lumi"]
        self.collectionChats = self.db["chats_lumi"]
        self.resCounting = 0

        self.countTrain = 2

        self.YDL_OPTIONS = {"format": "bestaudio", "noplaylist": True}
        self.ytdl = YoutubeDL(self.YDL_OPTIONS)
        self.FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}

        self.direction = "E:/Programacion/python/IA/lumi/audios/res.mp3"

        self.playlistGuild = {}
        self.is_playing = False

        self.temporalListening = []
        self.initialTime = 0

    def response(self, msg, arguments):
        try:
            arguments = arguments.lower()

            resBot = ""

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
                if re.search("\n", res):
                    resBot = res.split("\n")
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
            return ["tuve un error"]

    async def functions(self, msg, arguments):
        try:
            argumentsOrg = arguments
            arguments = arguments.lower().replace("ó", "o").replace("é", "e").replace(",", "")
            
            resState = False

            if re.search("reproduce", arguments) or re.search("play", arguments): 
                new = str(arguments).replace("reproduce", "").replace("puedes", "").replace("reproducir", "").strip()

                link = self.search_yt(argumentsOrg)
                voice_channel = msg.author.voice.channel

                if msg.guild.voice_client is None or not msg.guild.voice_client.is_connected():
                    if not voice_channel:
                        await msg.channel.send("No estás en ningún canal")
                        return True
                    await voice_channel.connect()
                    if msg.guild.voice_client == None:
                        await msg.channel.send("No me pude conectar al canal de voz")
                        return True
                else:
                    await msg.guild.voice_client.move_to(voice_channel)

                await self.play_music(msg, link)

                resState = True
            elif re.search("pausa", arguments) or re.search("pause", arguments):
                if msg.guild.voice_client.is_playing():
                    msg.guild.voice_client.pause()
                else: 
                    await msg.send("No se está reproduciendo música")
                resState = True
            elif re.search("sigue reproduciendo", arguments) or re.search("resume", arguments):
                if msg.guild.voice_client.is_paused():
                    msg.guild.voice_client.resume()
                else: 
                    await msg.send("No hay música pausada")
                resState = True
            elif re.search("cambia", arguments) and re.search("cancion", arguments) or re.search("salta", arguments) and re.search("cancion", arguments) or re.search("skip", arguments):
                if msg.guild.id in self.playlistGuild:
                    if len(self.playlistGuild[msg.guild.id]) > 1:
                        if msg.guild.voice_client != None and msg.guild.voice_client:
                            msg.guild.voice_client.stop()
                            self.play_next(msg)
                            await msg.channel.send("Se cambió la canción")
                    elif len(self.playlistGuild[msg.guild.id]) == 1:
                        if msg.guild.voice_client != None and msg.guild.voice_client:
                            msg.guild.voice_client.stop()
                            self.playlistGuild[msg.guild.id].pop(0)
                            await msg.channel.send("Se cambió la canción")
                    else:
                        await msg.channel.send("No sigue ninguna canción")
                else:
                    await msg.channel.send("No hay ninguna canción")
                resState = True
            elif re.search("cuales", arguments) and re.search("canciones", arguments) or re.search("muestra", arguments) and re.search("lista", arguments) or re.search("que", arguments) and re.search("canciones", arguments) or re.search("queue", arguments):
                if not msg.guild.id in self.playlistGuild:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                if len(self.playlistGuild[msg.guild.id]) == 0:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                text = ""

                for i in range(0, len(self.playlistGuild[msg.guild.id])):
                    text += f"\n{i + 1} - {self.playlistGuild[msg.guild.id][i]['title']}"

                await msg.channel.send(text)

                resState = True
            elif re.search("cuantas", arguments) and re.search("canciones", arguments):
                if not msg.guild.id in self.playlistGuild:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                if len(self.playlistGuild[msg.guild.id]) == 0:
                    await msg.channel.send("No hay ninguna canción")
                    return True

                await msg.channel.send(f"Faltan {len(self.playlistGuild[msg.guild.id])} canciones")

                resState = True
            elif re.search("elimina", arguments) and re.search("todas", arguments) and re.search("canciones", arguments):
                if not msg.guild.id in self.playlistGuild:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                if len(self.playlistGuild[msg.guild.id]) == 0:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                del self.playlistGuild[msg.guild.id]

                await msg.channel.send(f"Se eliminaron todas las canciones")
                resState = True
            elif re.search("elimina", arguments) and re.search("cancion", arguments) and len(re.findall("[0-9]", arguments)) != 0:
                if not msg.guild.id in self.playlistGuild:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                if len(self.playlistGuild[msg.guild.id]) == 0:
                    await msg.channel.send("No hay ninguna canción")
                    return True
                
                positions = re.findall("[0-9]", arguments)
                initial = False
                deleteds = []

                for position in positions:
                    if int(position) == 1:
                        initial = True

                    for i, object in enumerate(self.playlistGuild[msg.guild.id]):
                        if object["position"] == int(position):
                            deleteds.append(self.playlistGuild[msg.guild.id][i])
                            self.playlistGuild[msg.guild.id].pop(i)

                for i, object in enumerate(self.playlistGuild[msg.guild.id]):
                    if object["position"] == int(position):
                        self.playlistGuild[msg.guild.id]["position"] = i + 1

                if initial:
                    msg.guild.voice_client.stop()
                    self.play_next(msg, True)

                deletedString = ""
                for i, deleted in enumerate(deleteds):
                    deletedString += f"{deleted['position']} - {deleted['title']}\n"

                await msg.channel.send(f"Se eliminaron las siguientes canciones:\n{deletedString}")

                resState = True
            elif re.search("sal", arguments) and re.search("canal", arguments) or re.search("salte", arguments) and re.search("canal", arguments):
                if not msg.guild.voice_client is None:
                    if msg.guild.voice_client.is_connected():
                        await msg.guild.voice_client.disconnect()
                resState = True

            return resState
        except Exception as err:
            print(err)
            await msg.channel.send("Tuve un error")
            return True
    
    async def get_song(self, msg, link):
        message = await msg.channel.send("Buscando...")
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(link, download=False))
        #song = data["url"]

        if not msg.guild.id in self.playlistGuild:
            self.playlistGuild[msg.guild.id] = [
                {
                    "title": data["title"],
                    "url": data["url"],
                    "position": 1,
                    "persona": f"{msg.author.name}#{msg.author.discriminator}"
                }
            ]
            await message.edit(content=f"Reproduciendo: {self.playlistGuild[msg.guild.id][0]['title']}")
        else:
            self.playlistGuild[msg.guild.id].append({
                    "title": data["title"],
                    "url": data["url"],
                    "position": len(self.playlistGuild[msg.guild.id]) + 1,
                    "persona": f"{msg.author.name}#{msg.author.discriminator}"
                })
            await message.edit(content=f"Se agregó la canción {data['title']}")
            return True

    async def play_music(self, msg, link):
        try:
            await self.get_song(msg, link)

            if not msg.guild.voice_client.is_playing():
                player = discord.FFmpegPCMAudio(self.playlistGuild[msg.guild.id][0]["url"], **self.FFMPEG_OPTIONS)
                msg.guild.voice_client.play(player, after=lambda e: self.play_next(msg))

        except Exception as err:
            print(err)

    def play_next(self, msg):
        if len(self.playlistGuild[msg.guild.id]) > 0:

            self.playlistGuild[msg.guild.id].pop(0)

            url = self.playlistGuild[msg.guild.id][0]["url"]

            player = discord.FFmpegPCMAudio(url, **self.FFMPEG_OPTIONS)
            msg.guild.voice_client.play(player, after=lambda e: self.play_next(msg))
        else:
            self.is_playing = False

    async def skip(self, ctx):
        if ctx.voice_client != None and ctx.voice_client:
            ctx.voice_client.stop()
            await self.play_music(ctx)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if str(message.channel.type) == "private":
            res = self.response(message, message.content)
            for messageRes in res:
                await message.channel.send(messageRes)
        if self.collectionChannels.find_one({"channel": message.channel.id}) and not message.content.startswith("l!") and not message.content.startswith("#"):
            resFunctions = await self.functions(message, message.content)
            if resFunctions:
                return
            res = self.response(message, message.content)
            for messageRes in res:
                await message.channel.send(messageRes)
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
        res = self.response(ctx, arguments)
        
        for message in res:
            await ctx.send(message)

    def search_yt(self, item):

        url_pattern = "https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)"
        link = ""

        if len(re.findall(url_pattern, item)) > 0:
            link = re.findall(url_pattern, item)[0]
        else:
            query_string = parse.urlencode({"search_query": item})
            html_content = request.urlopen(f"http://www.youtube.com/results?{query_string}")

            link = html_content.read().decode('utf-8')

        search_results = re.findall('\\/watch\\?v=(.{11})', link)
    
        return search_results[0]

async def setup(client):
    await client.add_cog(AI_cog(client))