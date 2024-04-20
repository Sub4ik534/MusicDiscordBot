import discord
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
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    queues = {}
    voice_clients = {}
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                      'options': '-vn -filter:a "volume=0.25"'}

    def queue_song(guild_id, song):
        if guild_id not in queues:
            queues[guild_id] = []
        queues[guild_id].append(song)

    def play_next_song(guild_id):
        if queues[guild_id]:
            song = queues[guild_id].pop(0)
            player = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options)
            voice_clients[guild_id].play(player, after=lambda e: play_next_song(guild_id) if e is None else None)

    @client.event
    async def on_ready():
        print(f'{client.user} готов к работе')

    @client.event
    async def on_message(message):
        if message.content.startswith("/play"):
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

                url = message.content.split()[1]
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

                song = data['url']
                player = discord.FFmpegOpusAudio(song, **ffmpeg_options)

                voice_clients[message.guild.id].play(player)
                song = {'url': data['url']}
                queue_song(message.guild.id, song)
                if not voice_client.is_playing():
                    play_next_song(message.guild.id)
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

                song = {'url': video_url}
                queue_song(message.guild.id, song)
                if not voice_clients[message.guild.id].is_playing():
                    play_next_song(message.guild.id)

                player = discord.FFmpegOpusAudio(video_url, **ffmpeg_options)
                voice_clients[message.guild.id].play(player)

                response = f"Играет: {track_name} от {artist_name}"
            except Exception as e:
                response = f"Проблемы при обработке ссылки из Spotify: {e}"
            await message.channel.send(response)

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

        if message.content.startswith("/stop"):
            try:
                voice_clients[message.guild.id].stop()
            except Exception as e:
                print(e)

    client.run(TOKEN)