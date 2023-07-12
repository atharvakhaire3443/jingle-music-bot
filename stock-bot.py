import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import json
import yt_dlp as youtube_dl
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from discord import FFmpegPCMAudio
from discord import opus
import time

opus_encoder = discord.opus.Encoder()

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

queue = []
is_playing = False
is_paused = False

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
CHANNEL = int(os.getenv('CHANNEL'))
GOOGLE_KEY = os.getenv('GOOGLE_API_KEY')
path = '/Users/atharvakhaire/Documents/CS677/audioDownloads/'

bot = commands.Bot(command_prefix='!', intents=intents)


def getVideoLink(query):
    try:
        youtube = build('youtube', 'v3', developerKey=GOOGLE_KEY)
        search_response = youtube.search().list(q=query, part='id', maxResults=1, type='video').execute()
        id = search_response['items'][0]['id']['videoId']
        response = youtube.videos().list(part='contentDetails', id=id).execute()
        duration = response['items'][0]['contentDetails']['duration']
        link = f"http://www.youtube.com/watch?v={id}"
        return [link, duration]
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def downloadAudio(subject):
    content = getVideoLink(subject)
    options = {
        'format': 'bestaudio/best',
        'outputmpl': path + '%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with youtube_dl.YoutubeDL(options) as ydl:
        info = ydl.extract_info(content[0], download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([content[0]])

    return [filename, content[1]]


@bot.event
async def on_ready():
    guild = discord.utils.find(lambda g: g.name == GUILD, bot.guilds)
    channel = bot.get_channel(CHANNEL)

    print(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

    if channel:
        await channel.send("I'm back, bitches!!!")
    else:
        print('Channel not found')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


@bot.command()
async def RukJaa(ctx):
    global is_paused

    voice_state = ctx.message.guild.voice_client
    if voice_state and voice_state.is_playing():
        voice_state.pause()
        is_paused = True
        await ctx.send("Playback paused.")
    else:
        await ctx.send("No audio is currently playing.")


@bot.command()
async def Chal(ctx):
    global is_paused

    voice_state = ctx.message.guild.voice_client
    if voice_state and voice_state.is_paused():
        voice_state.resume()
        is_paused = False
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("Playback is not paused.")


@bot.command()
async def AageJaa(ctx):
    voice_state = ctx.message.guild.voice_client
    if voice_state and (voice_state.is_playing() or is_paused):
        voice_state.stop()
        await ctx.send("Skipped to the next song.")
    else:
        await ctx.send("No audio is currently playing.")


@bot.command()
async def Baja(ctx):
    channel = bot.get_channel(CHANNEL)
    if ctx.author.voice:
        subject = ctx.message.content[7:].strip().replace(' ', '+')
        deets = downloadAudio(subject + '+official+audio')
        filename = deets[0]
        duration = deets[1]
        voice_channel = ctx.author.voice.channel
        voice_state = ctx.message.guild.voice_client

        # Add the song to the queue
        queue.append((filename, duration))

        if voice_state is None:
            voice_client = await voice_channel.connect()

            # Start playing the queue if it was empty
            if len(queue) == 1:
                await play_queue(voice_client, channel)
        else:
            await channel.send('Added to queue: ' + filename)
    else:
        await channel.send("You need to be in a voice channel to use this command.")


async def play_queue(voice_client, channel):
    global is_playing, is_paused
    # Check if the queue is empty
    if not queue:
        await channel.send('Queue is empty.')
        is_playing = False
        await voice_client.disconnect()  # Disconnect the bot from the voice channel
        return

    # Get the first song from the queue
    song = queue[0]
    filename = song[0]
    duration = song[1]

    audio_source = FFmpegPCMAudio(filename.replace('webm', 'mp3'))
    voice_client.play(audio_source)

    await channel.send('Playing ' + filename)
    is_playing = True

    # Wait for the song to finish playing
    while voice_client.is_playing() or is_paused:
        await asyncio.sleep(1)

    # Delete the file after playing
    os.remove(filename.replace('webm', 'mp3'))

    # Remove the finished song from the queue
    queue.pop(0)

    # Play the next song in the queue
    await play_queue(voice_client, channel)


bot.run(TOKEN)
