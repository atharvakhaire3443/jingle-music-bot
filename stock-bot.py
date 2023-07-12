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

play_lock = asyncio.Lock()

opus_encoder = discord.opus.Encoder()

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

queue = []
is_playing = False
is_paused = False
filename = ''

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
async def rukjaa(ctx):
    global is_paused

    voice_state = ctx.message.guild.voice_client
    if voice_state and voice_state.is_playing():
        voice_state.pause()
        is_paused = True
        await ctx.send("Playback paused.")
    else:
        await ctx.send("No audio is currently playing.")
    await ctx.message.delete()


@bot.command()
async def chal(ctx):
    global is_paused

    voice_state = ctx.message.guild.voice_client
    if voice_state and voice_state.is_paused():
        voice_state.resume()
        is_paused = False
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("Playback is not paused.")
    await ctx.message.delete()


@bot.command()
async def aagejaa(ctx):
    voice_state = ctx.message.guild.voice_client
    if voice_state and (voice_state.is_playing() or is_paused):
        voice_state.stop()
        await ctx.send("Skipped to the next song.")
    else:
        await ctx.send("No audio is currently playing.")
    await ctx.message.delete()

@bot.command()
async def nikal(ctx):
    voice_state = ctx.message.guild.voice_client

    if voice_state:
        if voice_state.is_playing() or voice_state.is_paused():
            voice_state.stop()
        #os.remove(filename.replace('webm', 'mp3'))
        await voice_state.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I am not connected to a voice channel.")
    await ctx.message.delete()

@bot.command()
async def gaananikaal(ctx, index: int):
    if index < 1 or index > len(queue):
        await ctx.send("Invalid song index.")
    else:
        removed_song = queue.pop(index - 1)
        filename = removed_song[0]
        os.remove(filename.replace('webm', 'mp3'))
        await ctx.send(f"Removed song at index {index} from the queue.")
        channel = bot.get_channel(CHANNEL)
        await update_queue_message(channel)  # Update the queue display
    await ctx.message.delete()


@bot.command()
async def baja(ctx):
    channel = bot.get_channel(CHANNEL)
    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel
        voice_state = ctx.message.guild.voice_client

        # Add the song to the queue
        subject = ctx.message.content[6:].strip().replace(' ', '+')
        deets = downloadAudio(subject + '+official+audio')
        filename = deets[0]
        duration = deets[1]

        async with play_lock:
            queue.append((filename, duration))

        if voice_state is None:
            voice_client = await voice_channel.connect()

            # Start playing the queue if it was empty
            if len(queue) == 1:
                await play_queue(voice_client, channel)
        else:
            await channel.send('Added to queue: ' + subject)

        await update_queue_message(channel)  # Update the queue display
    else:
        await channel.send("You need to be in a voice channel to use this command.")
    await ctx.message.delete()

async def play_queue(voice_client, channel):
    global is_playing, is_paused

    # Check if the queue is empty
    if not queue:
        await channel.send('Queue is empty.')
        is_playing = False
        await voice_client.disconnect()  # Disconnect the bot from the voice channel
        return

    # Get the first song from the queue
    async with play_lock:
        filename, duration = queue[0]
        queue.pop(0)

    audio_source = FFmpegPCMAudio(filename.replace('webm', 'mp3'))
    voice_client.play(audio_source)

    await channel.send('Playing ' + filename)
    is_playing = True

    # Wait for the song to finish playing
    while voice_client.is_playing() or is_paused:
        await asyncio.sleep(1)

    # Delete the file after playing
    os.remove(filename.replace('webm', 'mp3'))

    # Play the next song in the queue
    await play_queue(voice_client, channel)

@bot.command()
async def kyabajaray(ctx):
    channel = bot.get_channel(CHANNEL)
    await update_queue_message(channel) # Update the queue display
    await ctx.message.delete()

async def update_queue_message(channel):
    if queue:
        queue_message = "------------------------------------------------\nCurrent Queue:\n"
        for i, (filename, duration) in enumerate(queue, start=1):
            queue_message += f"{i}. {filename} - Duration: {duration}\n"
    else:
        queue_message = "Queue is empty."

    await channel.send(queue_message)

bot.run(TOKEN)
