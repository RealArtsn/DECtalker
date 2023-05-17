import sys, os, subprocess as sp, io, sqlite3, datetime
import discord 
from pydub import AudioSegment
from discord import app_commands
import logging


class Client(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        # sync commands if 'sync' argument provided
        if 'sync' in sys.argv:
            print('Syncing slash commands globally...')
            await DECtalker.tree.sync()
            print('Exiting...')
            await self.close()
        # create preference table if not existant
        initialize_database()
    # automatically disconnect from voice channel if empty
    async def on_voice_state_update(member, before, after, _):
        # disconnect if last one in channel
        try:
            if len(DECtalker.voice_clients[0].channel.members) == 1:
                await DECtalker.voice_clients[0].disconnect()
        # Event can fire when not in call
        except IndexError:
            pass

# set gateway intents, only voice states required for voice
intents = discord.Intents.default()
intents.voice_states = True
DECtalker = Client(intents=intents)

# logging handler
DECtalker.log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')


# slash command tree
DECtalker.tree = app_commands.CommandTree(DECtalker)

async def text_to_speech(text, user, voice_client, language, speed, voice):
    if voice_client is None:
        return "Not connected to a voice channel."
    if not text:
        return "Invalid input."


    # Get preferences from database if values are not passed
    if language is None:
        language = get_preference(user, 'language')
    else:
        language = language.value
    if voice is None:
        voice = get_preference(user, 'voice')
    else:
        voice = voice.value
    try:
        speed = float(speed)
        if speed > 3 or speed < 0.1:
            raise ValueError
    except ValueError:
        return "speed must be a decimal less than 3"
    # execute dectalk
    # phoneme on is necesary for singing
    # stdout:raw allows piping audio to discord
    result = sp.run([f'dectalk/dist/say','-pre','[:phoneme on]', '-l', str(language),'-s', str(voice), '-a', text, '-e', '1', '-fo', 'stdout:raw'], stdout=sp.PIPE, stderr=sp.PIPE)    
    if result.returncode != 0:
        return result.stderr

    frame_rate = round(96000 * speed)

    # stream audio bytes from stdout
    audio: AudioSegment = AudioSegment.from_raw(io.BytesIO(result.stdout), sample_width=2, frame_rate=11000, channels=1)
    audio = audio.set_frame_rate(frame_rate)
    audio = discord.PCMAudio(io.BytesIO(audio.raw_data))
    
    # "speak" in the voice channel
    try:
        voice_client.play(audio)
        return 'Speaking.'
    except discord.errors.ClientException: # typically happens when the bot is already speaking
        return 'Already Speaking'


# log the command to a file
def log_command(id, message):
    with open('voice.log','a') as log:
        log.write(f"{datetime.datetime.now().isoformat()},{id},{message}\n")

# In this order from 0 to 8, voices available from DECtalk binary
DECtalker.VOICES = ('Paul','Betty','Harry', 'Frank', 'Dennis', 'Kit', 'Ursula', 'Rita', 'Wendy')

# connect to voice channel of interaction user
@DECtalker.tree.command(name = "connect", description = "Connects to voice channel.")
async def slash(interaction:discord.Interaction):
    # disconnect all existing voice clients
    for voice_client in DECtalker.voice_clients:
        await voice_client.disconnect()
    voice_client = await interaction.user.voice.channel.connect()
    response = 'Connected successfully.' if voice_client.is_connected() else 'Connecting failed.'
    await interaction.response.send_message(response ,ephemeral=True)

# Disconnect from all connected voice clients    
@DECtalker.tree.command(name = "disconnect", description = "Disconnects from voice channel.")
async def slash(interaction:discord.Interaction):
    await interaction.response.send_message('Disconnecting...', ephemeral=True)
    for voice_client in DECtalker.voice_clients:
        await voice_client.disconnect()
DECtalker.language_choices = [
    app_commands.Choice(name='English (US)', value='us'),
    app_commands.Choice(name='English (UK)', value='uk'),
    app_commands.Choice(name='Spanish', value='sp'),
    app_commands.Choice(name='German', value='gr'),
    app_commands.Choice(name='French', value='fr'),
    app_commands.Choice(name='Latin', value='la')
]
# Speak in voice channel
@DECtalker.tree.command(name = "say", description = "Text to speech")
@app_commands.choices(language=DECtalker.language_choices)
# dectalk takes a value from 0-9 for a voice
@app_commands.choices(voice=[
    app_commands.Choice(name=n, value=str(v)) for v, n in enumerate(DECtalker.VOICES)
])
async def slash(interaction:discord.Interaction, text:str, language: app_commands.Choice[str] = None, speed:str = '1', voice: app_commands.Choice[str] = None):
    log_command(interaction.user.id, text)
    # initiate text to speech in connected voice channel     
    response = await text_to_speech(
        text, 
        interaction.user.id,
        voice_client=DECtalker.voice_clients[0], 
        language=language, 
        speed=speed, 
        voice=voice
    )
    await interaction.response.send_message(response, ephemeral=True)

# command to store tts preferences in sql table
@DECtalker.tree.command(name = "voice_preference", description = "Text to speech language preference")
@app_commands.choices(language=DECtalker.language_choices)
@app_commands.choices(voice=[
    app_commands.Choice(name=n, value=str(v)) for v, n in enumerate(DECtalker.VOICES)
])
async def slash(interaction:discord.Interaction, language: app_commands.Choice[str], voice: app_commands.Choice[str]):
    response = f'Language preference set to: \n{language.name}\n{voice.name}'
    print(f'{interaction.user.name} in {interaction.guild.name} swapped TTS preference to: {language.name}, {voice.name}')
    update_preferences(interaction.user.id, language.value, voice.value)
    await interaction.response.send_message(response, ephemeral=True)
    return

# wrapper to execute query on the database
def run_query(query):
    con = sqlite3.connect('DECtalker.db')
    cur = con.cursor()
    response = cur.execute(query).fetchall()
    con.commit()
    con.close()
    return response

def initialize_database():
    query = 'CREATE TABLE IF NOT EXISTS preferences (id TEXT PRIMARY KEY UNIQUE, language TEXT DEFAULT "us", voice TEXT DEFAULT "0")'
    run_query(query)

def update_preferences(id, language, voice):
    validate_user(id)
    run_query(f'UPDATE preferences SET language = "{language}", voice = "{voice}" WHERE id = "{id}"')

def get_preference(id, preference):
    # validate user to generate preferences if none exist
    validate_user(id)
    return run_query(f'SELECT {preference} FROM preferences WHERE id = "{id}"')[0][0]
    
# add user to table if not exists
def validate_user(id):
    run_query(f'INSERT OR IGNORE INTO preferences(id) VALUES("{id}")')


# Run with token or prompt if one does not exist
try:
    with open('token', 'r') as token:
        DECtalker.run(token.read(), log_handler=DECtalker.log_handler)
except FileNotFoundError:
    print('Token not found. Input bot token and press enter or place it in a plaintext file named `token`.')
    token_text = input('Paste token: ')
    with open('token','w') as f:
        f.write(token_text)
        DECtalker.run(token_text, log_handler=DECtalker.log_handler)
