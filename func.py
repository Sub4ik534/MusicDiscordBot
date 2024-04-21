import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv


def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    client_id_ = os.getenv('YOUR_CLIENT_ID')
    client_secret_ = os.getenv('YOUR_CLIENT_SECRET')
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id_, client_secret=client_secret_))
    intents = discord.Intents.all()
    client = commands.Bot(command_prefix='', intents=intents)
    client.remove_command('help')

    queues = {}
    voice_clients = {}
    loops = {}
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                      'options': '-vn -filter:a "volume=0.25"'}

    def queue_song(guild_id, song):
        if guild_id not in queues:
            queues[guild_id] = []
        queues[guild_id].append(song)
        if len(queues[guild_id]) == 1:
            play_next_song(guild_id)

    def play_next_song(guild_id):
        if queues[guild_id] and not voice_clients[guild_id].is_playing():
            song = queues[guild_id].pop(0)
            player = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options)
            voice_clients[guild_id].play(player, after=lambda e: handle_end_of_song(e, guild_id, song))

    def handle_end_of_song(error, guild_id, song):
        if error is None:
            if loops.get(guild_id, False):
                queues[guild_id].insert(0, song)
            play_next_song(guild_id)

    @client.event
    async def on_ready():
        print(f'{client.user} готов к работе')

    @client.event
    async def on_message(message):
        if message.content.startswith("/play"):
            args = message.content.split()
            if len(args) < 2:
                await message.channel.send("Пожалуйста, укажите название трека или URL.")
                return

            track_query = ' '.join(args[1:])

            try:
                voice_client = await message.author.voice.channel.connect()
                voice_clients[voice_client.guild.id] = voice_client
            except Exception as e:
                print(e)

            try:
                voice_client = voice_clients.get(message.guild.id)
                if not voice_client:
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client

                if "http" not in track_query:
                    track_query = f"ytsearch:{track_query}"

                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(track_query, download=False))

                if 'entries' in data:
                    data = data['entries'][0]

                song = {'url': data['url'], 'title': data.get('title', 'Unknown')}

                if message.guild.id not in voice_clients:
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client

                queue_song(message.guild.id, song)

            except Exception as e:
                print(e)

        if "open.spotify.com/track/" in message.content:
            track_id = message.content.split('track/')[1].split('?')[0]
            try:
                track_info = sp.track(track_id)
                track_name = track_info['name']
                artist_name = track_info['artists'][0]['name']
                search_query = f"{track_name} {artist_name} audio"

                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{search_query}",
                                                                                     download=False))
                video_url = results['entries'][0]['url']
                print(video_url)
                video_title = results['entries'][0].get('title', track_name)

                song = {'url': video_url, 'title': video_title}
                queue_song(message.guild.id, song)
                if not voice_clients[message.guild.id].is_playing():
                    play_next_song(message.guild.id)

            except Exception as e:
                print(e)

        if message.content.startswith("/loop"):
            guild_id = message.guild.id
            loops[guild_id] = not loops.get(guild_id, False)
            state = "включено" if loops[guild_id] else "выключено"
            await message.channel.send(f"Зацикливание {state}")

        if message.content.startswith("/pause"):
            try:
                voice_clients[message.guild.id].pause()
            except Exception as e:
                print(e)

        if message.content.startswith("/resume"):
            try:
                voice_clients[message.guild.id].resume()
            except Exception as e:
                print(e)

        if message.content.startswith("/leave"):
            try:
                voice_clients[message.guild.id].stop()
                await voice_clients[message.guild.id].disconnect()
            except Exception as e:
                print(e)

        if message.content.startswith("/next"):
            if queues[message.guild.id]:
                voice_clients[message.guild.id].stop()
                play_next_song(message.guild.id)
            else:
                await message.channel.send("В очереди больше нет треков")

        if message.content.startswith("/stop"):
            try:
                voice_clients[message.guild.id].stop()
            except Exception as e:
                print(e)

        if message.content.startswith("/clear"):
            voice_clients[message.guild.id].stop()
            queues[message.guild.id] = []
            await message.channel.send("Очередь очищена")

        if message.content.startswith("/help"):
            await message.channel.send("/play 'ссылка' - команда для запуска музыки \n"
                                       "/pause - поставить трек на паузу \n"
                                       "/resume - включить трек \n"
                                       "/stop - выключает трек \n"
                                       "/loop - команда для зацикливания текущего трека \n"
                                       "/leave - комманда, чтобы бот покинул канал\n"
                                       "/next - следующий трек из очереди\n"
                                       "/clear - очистка очереди")

    client.run(TOKEN)