import os
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


# if not discord.opus.is_loaded():
#     discord.opus.load_opus('/opt/homebrew/Cellar/opus/1.4/lib/libopus.0.dylib')

opus_encoder = discord.opus.Encoder()

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
CHANNEL = int(os.getenv('CHANNEL'))
GOOGLE_KEY = os.getenv('GOOGLE_API_KEY')
path = '/Users/atharvakhaire/Documents/CS677/audioDownloads/'

bot = commands.Bot(command_prefix='!', intents=intents)

def getVideoLink(query):
    try:
        youtube = build('youtube','v3',developerKey=GOOGLE_KEY)
        search_response = youtube.search().list(q=query,part='id',maxResults=1,type='video').execute()
        id = search_response['items'][0]['id']['videoId']
        link = f"http://www.youtube.com/watch?v={id}"
        return link
    except HttpError as error:
        print(f"An error occured: {error}")
        return None

def downloadAudio(subject):
    url = getVideoLink(subject)
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
        info = ydl.extract_info(url,download = False)
        filename = ydl.prepare_filename(info)
        ydl.download([url])
    
    return filename

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
    channel = bot.get_channel(CHANNEL)
    if message.author == bot.user:
        return
    if message.content.startswith('!answerME'):
        if message.author.voice:
            subject = message.content[10:].strip().replace(' ','+')
            filename = downloadAudio(subject+'+official+audio')
            voice_channel = message.author.voice.channel
            voice_state = message.guild.voice_client
            if voice_state is None:
                voice_client = await voice_channel.connect()
            audio_source = FFmpegPCMAudio(filename.replace('webm','mp3'))
            await message.channel.send('Playing '+filename)
            voice_client.play(audio_source)
        else:
            await message.channel.send("You need to be in a voice channel to use this command.")

    await bot.process_commands(message)        

bot.run(TOKEN)
