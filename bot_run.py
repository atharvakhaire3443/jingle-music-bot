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
import random
import sqlite3
import pandas as pd
import uuid

conn = sqlite3.connect('jingle.db')

cur = conn.cursor()

playlist_file = 'playlist.txt'

play_lock_df = pd.DataFrame(columns=['guild','lock','is_playing','is_paused'])

opus_encoder = discord.opus.Encoder()

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

# client = discord.Bot(intents=intents)

queue = []
is_playing = False
is_paused = False
filename = ''

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_KEY = os.getenv('GOOGLE_API_KEY')
path = '/Users/atharvakhaire/Documents/CS677/audioDownloads/'

bot = commands.Bot(command_prefix='!', intents=intents)

def find_song_in_playlist(file_path, search_string):
    with open(file_path, 'r') as file:
        for line in file:
            if search_string in line:
                return True
    return False

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
            'preferredcodec': 'flac',
            'preferredquality': '320',
        }],
    }

    with youtube_dl.YoutubeDL(options) as ydl:
        info = ydl.extract_info(content[0], download=False)
        filename = ydl.prepare_filename(info)
        ydl.download([content[0]])

    return [filename, content[1]]


@bot.event
async def on_ready():
    cur.execute('select * from servers')
    guild_data = cur.fetchall()
    print(guild_data)
    print(bot.guilds)

    server_names = [guild.name for guild in bot.guilds] 

    for server in server_names:
        flag = False
        for data in guild_data:
            if server == data[0]:
                flag = True
        if flag == False:
            cur.execute(f"insert into servers(name,channel_id) values(?,?)",(server,1))
            conn.commit()
    
    for data in guild_data:
        guild_name = data[0]
        channel_id = data[1]
        print(guild_name)
        
        guild = discord.utils.get(bot.guilds, name=guild_name)
        
        if guild:
            existing_channel_names = {c.name for c in guild.text_channels}
            print(existing_channel_names)
            
            print(
                f'{bot.user} is connected to the following guild:\n'
                f'{guild.name}(id: {guild.id})'
            )
            
            if 'jingle-space' in existing_channel_names:
                print(f'Text channel already exists in {guild.name}')
            else:
                # Create a new text channel
                new_channel = await guild.create_text_channel('jingle-space')
                print(new_channel)
                print(f'Created a new text channel in {guild.name}')
                await new_channel.send("Welcome to Jingle-Space! Feel free to play some tunes here.")
                cur.execute(f"update servers set channel_id = ? where name = ?",(new_channel.id,guild_name))
                conn.commit()
        
        else:
            print('Guild not found')
        play_lock_df.loc[len(play_lock_df)] = [guild_name,asyncio.Lock(),False,False]
    print(play_lock_df)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.command()
async def pause(ctx):
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
async def resume(ctx):
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
async def next(ctx):
    voice_state = ctx.message.guild.voice_client
    is_paused = list(play_lock_df[play_lock_df['guild'] == ctx.guild.name]['is_paused'])[0]
    if voice_state and (voice_state.is_playing() or is_paused):
        voice_state.stop()
        await ctx.send("Skipped to the next song.")
    else:
        await ctx.send("No audio is currently playing.")
    await ctx.message.delete()

@bot.command()
async def disconnect(ctx):
    voice_state = ctx.message.guild.voice_client

    if voice_state:
        if voice_state.is_playing() or voice_state.is_paused():
            voice_state.stop()
        #os.remove(filename.replace('webm', 'mp3'))
        for song in queue:
            queue.remove(song)
            if not (find_song_in_playlist("playlist.txt", filename)):
                os.remove(song.replace('webm', 'flac'))
        await voice_state.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I am not connected to a voice channel.")
    await ctx.message.delete()

@bot.command()
async def remove(ctx, index: int):
    if index < 1 or index > len(queue):
        await ctx.send("Invalid song index.")
    else:
        removed_song = queue.pop(index - 1)
        filename = removed_song
        #os.remove(filename.replace('webm', 'mp3'))
        if not (find_song_in_playlist("playlist.txt", filename)):
        #os.remove(filename.replace('webm', 'mp3'))
            os.remove(filename.replace("webm","flac"))
        await ctx.send(f"Removed song at index {index} from the queue.")
        cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
        row = cur.fetchone()

        if row is None:
            await ctx.send("This server's channel ID is not found in the database.")
            return

        channel_id = row[0]
        channel = bot.get_channel(channel_id)
        await update_queue_message(channel,ctx)  # Update the queue display
    await ctx.message.delete()

@bot.command()
async def shift(ctx, original_index: int, final_index: int):

    cur.execute(f"select count(*) from global_queue where server_name = ?",(ctx.guild.name,))
    rows = cur.fetchall()
    if original_index < 1 or original_index > len(rows) or final_index < 1 or final_index > len(rows):
        await ctx.send("Invalid song index.")
    else:
        filename = queue.pop(original_index - 1)
        queue.insert(final_index-1,filename)
        await ctx.send(f"Shifted song at index {original_index} to index {final_index}.")
        cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
        row = cur.fetchone()

        if row is None:
            await ctx.send("This server's channel ID is not found in the database.")
            return

        channel_id = row[0]
        channel = bot.get_channel(channel_id)
        await update_queue_message(channel)
    await ctx.message.delete()

@bot.command()
async def play(ctx):
    # Fetch the server-specific channel ID from SQL based on ctx.guild.name
    cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
    row = cur.fetchone()

    if row is None:
        await ctx.send("This server's channel ID is not found in the database.")
        return

    channel_id = row[0]
    channel = bot.get_channel(channel_id)

    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel
        print(voice_channel)
        voice_state = ctx.message.guild.voice_client

        # Add the song to the queue
        subject = ctx.message.content[6:].strip().replace(' ', '+')
        deets = downloadAudio(subject + '+official+audio')
        filename = deets[0]
        duration = deets[1]
        print(ctx.guild.name)
        lock = list(play_lock_df[play_lock_df['guild'] == ctx.guild.name]['lock'])[0]
        async with lock:
            try:
                cur.execute(f"select max(queue_position) from global_queue where server_name = ?",(ctx.guild.name,))
                row = cur.fetchone()
                next_queue_position = int(row[0]) + 1
                cur.execute(f"insert into global_queue(instance_id,song_name,server_name,queue_position) values(?,?,?,?)",(str(uuid.uuid4()),filename,ctx.guild.name,next_queue_position))
                conn.commit()
            except:
                cur.execute(f"insert into global_queue(instance_id,song_name,server_name,queue_position) values(?,?,?,?)",(str(uuid.uuid4()),filename,ctx.guild.name,1))
                conn.commit()

        if voice_state is None:
            voice_client = await voice_channel.connect()

            # Start playing the queue if it was empty
            cur.execute(f"select count(queue_position) from global_queue where server_name = ?",(ctx.guild.name,))
            row = cur.fetchone()
            temp = row[0]
            if temp > 0:
                await play_queue(voice_client, channel, ctx)
        # else:
        #     await channel.send('Added to queue: ' + subject)

        await update_queue_message(channel,ctx)  # Update the queue display
    else:
        await channel.send("You need to be in a voice channel to use this command.")
    await ctx.message.delete()


async def play_queue(voice_client, channel, ctx):

    # Check if the queue is empty
    cur.execute(f"select count(queue_position) from global_queue where server_name = ?",(ctx.guild.name,))
    row = cur.fetchone()
    temp = row[0]
    if temp == 0:
        await channel.send('Queue is empty.')
        play_lock_df[play_lock_df['guild'] == ctx.guild.name]['is_playing'] = False
        await voice_client.disconnect()  # Disconnect the bot from the voice channel
        return

    await update_queue_message(channel,ctx)

   # Get the first song from the queue
    lock = list(play_lock_df[play_lock_df['guild'] == ctx.guild.name]['lock'])[0]
    async with lock:
        cur.execute(f"select song_name from global_queue where server_name = ? and queue_position = (select min(queue_position) from global_queue where server_name = ?)",(ctx.guild.name,ctx.guild.name))
        row = cur.fetchone()
        filename = row[0]

    audio_source = FFmpegPCMAudio(filename.replace("webm", "flac"))
    voice_client.play(audio_source)

    await channel.send('Playing ' + filename)
    play_lock_df[play_lock_df['guild'] == ctx.guild.name]['is_playing'] = True

    # Wait for the song to finish playing or being paused
    is_paused = list(play_lock_df[play_lock_df['guild'] == ctx.guild.name]['is_paused'])[0]
    while voice_client.is_playing() or is_paused:
        await asyncio.sleep(1)

    cur.execute(f"select song_name, instance_id from global_queue where server_name = ? and queue_position = (select min(queue_position) from global_queue where server_name = ?)",(ctx.guild.name,ctx.guild.name))
    row = cur.fetchone()
    current_song = row[0]
    instance_id = row[1]
    # Remove the song from the queue if it's the currently playing song
    lock = list(play_lock_df[play_lock_df['guild'] == ctx.guild.name]['lock'])[0]
    async with lock:
        if current_song == filename:
            cur.execute(f"delete from global_queue where server_name = ? and instance_id = ?",(ctx.guild.name,instance_id))
            conn.commit()

    cur.execute(f"select song_name from global_playlist")
    song_data = cur.fetchall()

    flag = False
    for data in song_data:
        song = data[0]
        if song == filename:
            flag = True
    
    if not flag:
        os.remove(filename.replace("webm", "flac"))

    # Play the next song in the queue
    await play_queue(voice_client, channel, ctx)

@bot.command()
async def displayqueue(ctx):
    cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
    row = cur.fetchone()

    if row is None:
        await ctx.send("This server's channel ID is not found in the database.")
        return

    channel_id = row[0]
    channel = bot.get_channel(channel_id)
    await update_queue_message(channel,ctx)

queue_message_id = None  # Store the ID of the queue display message

async def update_queue_message(channel,ctx):
    global queue_message_id

    # Delete the previous queue display message if it exists
    if queue_message_id:
        try:
            previous_message = await channel.fetch_message(queue_message_id)
            await previous_message.delete()
        except discord.NotFound:
            pass

    cur.execute(f"select song_name,queue_position from global_queue where server_name = ?",(ctx.guild.name,))
    rows = cur.fetchall()
    queue = []

    print(rows)

    for song in rows:
        queue.append([song[0],song[1]])
    print(queue)

    queue = sorted(queue, key=lambda x: x[1])

    print(queue)

    if queue:
        queue_message = "---------------------------------------------\nCurrent Queue:\n"
        for i, filename in enumerate(queue, start=1):
            queue_message += f"{i}. {filename}\n"
    else:
        queue_message = "Queue is empty."

    # Send the updated queue message and store its ID
    queue_display_message = await channel.send(queue_message)
    queue_message_id = queue_display_message.id

@bot.command()
async def addtoplaylist(ctx):
    cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
    row = cur.fetchone()

    if row is None:
        await ctx.send("This server's channel ID is not found in the database.")
        return

    channel_id = row[0]
    channel = bot.get_channel(channel_id)
    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel
        voice_state = ctx.message.guild.voice_client

        # Add the song to the playlist file
        subject = ctx.message.content[15:].strip().replace(' ', '+')
        deets = downloadAudio(subject + '+official+audio')
        filename = deets[0]
        duration = deets[1]

        cur.execute(f"select song_name from global_playlist where server_name = ?",(ctx.guild.name,))
        rows = cur.fetchall()

        flag = False
        for song in rows:
            if song[0] == filename:
                flag = True
        if not flag:
            cur.execute(f"insert into global_playlist(instance_id,song_name,server_name) values(?,?,?)",(str(uuid.uuid4()),filename,ctx.guild.name))
            conn.commit()

        await channel.send('Added to playlist: ' + subject)
    else:
        await channel.send("You need to be in a voice channel to use this command.")
    await ctx.message.delete()

@bot.command()
async def playplaylist(ctx):
    randomize = False
    cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
    row = cur.fetchone()

    if row is None:
        await ctx.send("This server's channel ID is not found in the database.")
        return

    channel_id = row[0]
    channel = bot.get_channel(channel_id)
    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel
        voice_state = ctx.message.guild.voice_client

        if ctx.message.content[14:].strip().replace(' ','') == 'random':
            randomize = True

        if voice_state is None:
            voice_client = await voice_channel.connect()

            # Read the songs from the playlist file

            cur.execute(f"select song_name from global_playlist where server_name = ?",(ctx.guild.name,))
            rows = cur.fetchall()

            # Shuffle the playlist if randomize is True
            if randomize:
                random.shuffle(rows)

            for song in rows:
                try:
                    cur.execute(f"select max(queue_position) from global_queue where server_name = ?",(ctx.guild.name,))
                    row = cur.fetchone()
                    next_queue_position = int(row[0]) + 1
                    cur.execute(f"insert into global_queue(instance_id,song_name,server_name,queue_position) values(?,?,?,?)",(str(uuid.uuid4()),filename,ctx.guild.name,next_queue_position))
                    conn.commit()
                except:
                    cur.execute(f"insert into global_queue(instance_id,song_name,server_name,queue_position) values(?,?,?,?)",(str(uuid.uuid4()),filename,ctx.guild.name,1))
                    conn.commit()

            # Start playing the queue if it was empty
            if len(queue) > 0 and not is_playing:
                await play_queue(voice_client, channel)
        else:
            await channel.send('I am already in a voice channel.')
    else:
        await channel.send("You need to be in a voice channel to use this command.")
    await ctx.message.delete()

@bot.command()
async def randomize(ctx):
    global queue

    cur.execute(f"select song_name from global_queue where server_name = ? and queue_position not in (select min(queue_position) from global queue where server_name = ?)",(ctx.guild.name,ctx.guild.name))
    rows = cur.fetchall()
    if len(rows) <= 2:
        await ctx.send("Queue does not have enough songs to be randomized.")
        return

    # Shuffle the queue starting from the second song
    random.shuffle(rows)

    cur.execute(f"delete from global_queue where server_name = ? and queue_position not in (select min(queue_position) from global_queue where server_name = ?)",(ctx.guild.name,ctx.guild.name))
    conn.commit()
    for song in rows:
            cur.execute(f"select max(queue_position) from global_queue where server_name = ?",(ctx.guild.name,))
            row = cur.fetchone()
            next_queue_position = int(row[0]) + 1
            cur.execute(f"insert into global_queue(instance_id,song_name,server_name,queue_position) values(?,?,?,?)",(str(uuid.uuid4()),song[0],ctx.guild.name,next_queue_position))
            conn.commit()

    cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
    row = cur.fetchone()

    if row is None:
        await ctx.send("This server's channel ID is not found in the database.")
        return

    channel_id = row[0]
    channel = bot.get_channel(channel_id)
    await update_queue_message(channel,ctx)
    await ctx.send("Queue has been randomized.")
    await ctx.message.delete()

@bot.command()
async def playlist(ctx):
    cur.execute(f"select song_name,instance_id from global_playlist where server_name = ?",(ctx.guild.name,))
    rows = cur.fetchall()

    if not rows:
        await ctx.send("No songs are currently on your playlist!")
        return

    print(rows)

    for song in rows:
        playlist.append([song[0],song[1]])
    print(playlist)

    if playlist:
        playlist_message = "---------------------------------------------\nPlaylist:\n"
        for i, filename in enumerate(playlist, start=1):
            playlist_message += f"{i}. {filename}\n"
    await ctx.send(playlist_message)
    await ctx.message.delete()

@bot.command()
async def removefromplaylist(ctx, instance_id):
    try:
        cur.execute(f"delete from global_playlist where server_name = ? and instance_id = ?",(ctx.guild.name,instance_id))
        conn.commit()
    except:
        await ctx.send("No such song exists in the playlist")

    cur.execute('SELECT channel_id FROM servers WHERE name = ?', (ctx.guild.name,))
    row = cur.fetchone()

    if row is None:
        await ctx.send("This server's channel ID is not found in the database.")
        return

    channel_id = row[0]
    channel = bot.get_channel(channel_id)
    await update_queue_message(channel,ctx)  # Update the queue display

    await ctx.send(f"Song removed.")
    await ctx.message.delete()

@bot.command()
async def flushplaylist(ctx):
    try:
        cur.execute(f"delete from global_playlist where server_name = ?",(ctx.guild.name,))
    except:
        await ctx.send("Playlist for this server does not exist")
    await ctx.send("Playlist flushed.")

@bot.command()
async def info(ctx):
    command_list = [
        "Commands:",
        "!play <song>: Play a song",
        "!pause: Pause the current playback",
        "!resume: Resume the paused playback",
        "!next: Skip to the next song",
        "!disconnect: Disconnect the bot from the voice channel",
        "!remove <index>: Remove a song from the queue",
        "!shift <original_index> <final_index>: Shift a song in the queue",
        "!queue: Display the current queue",
        "!addtoplaylist <song>: Add a song to the playlist",
        "!playplaylist [random]: Play the songs from the playlist",
        "!randomize: Randomize the current queue",
        "!playlist: Display the playlist",
        "!removefromplaylist <index>: Remove a song from the playlist"
    ]

    help_message = "\n".join(command_list)
    await ctx.send(help_message)


bot.run(TOKEN)
