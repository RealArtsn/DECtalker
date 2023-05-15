import sys, os, subprocess as sp, io
import discord 
from pydub import AudioSegment
from discord import app_commands

class Client(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        # sync commands if 'sync' argument provided
        if 'sync' in sys.argv:
            print('Syncing slash commands globally...')
            await DECtalker.tree.sync()
            print('Exiting...')
            await self.close()

# set gateway intents, only voice states required for voice
intents = discord.Intents.default()
intents.voice_states = True
DECtalker = Client(intents=intents)

# slash command tree
DECtalker.tree = app_commands.CommandTree(DECtalker)

async def text_to_speech(text, user, voice_client, language, speed, voice):
    if voice_client is None:
        return "Not connected to a voice channel."
    if not text:
        return "Invalid input."
    if not isinstance(language, str):
        language = language.value
    if not isinstance(voice, str):
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
        log.write(message)

# In this order from 0 to 8, voices available from DECtalk binary
DECtalker.VOICES = ('Paul','Betty','Harry', 'Frank', 'Dennis', 'Kit', 'Ursula', 'Rita', 'Wendy')

# connect to voice channel channel of interaction user
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

# Speak in voice channel
@DECtalker.tree.command(name = "say", description = "Text to speech")
@app_commands.choices(language=[
    app_commands.Choice(name='English (US)', value='us'),
    app_commands.Choice(name='English (UK)', value='uk'),
    app_commands.Choice(name='Spanish', value='sp'),
    app_commands.Choice(name='German', value='gr'),
    app_commands.Choice(name='French', value='fr'),
    app_commands.Choice(name='Latin', value='la')
])
# dectalk takes a value from 0-9 for a voice
@app_commands.choices(voice=[
    app_commands.Choice(name=n, value=str(v)) for v, n in enumerate(DECtalker.VOICES)
])
async def slash(interaction:discord.Interaction, text:str, language: app_commands.Choice[str] = 'us', speed:str = '1', voice: app_commands.Choice[str] = '0'):
    # initiate text to speech in connected voice channel     
    response = await text_to_speech(
        text, 
        interaction.user,
        voice_client=DECtalker.voice_clients[0], 
        language=language, 
        speed=speed, 
        voice=voice
    )
    await interaction.response.send_message(response, ephemeral=True)


# Run with token or prompt if one does not exist
try:
    with open('token', 'r') as token:
        DECtalker.run(token.read())        
except FileNotFoundError:
    print('Token not found. Input bot token and press enter or place it in a plaintext file named `token`.')
    token_text = input('Paste token: ')
    with open('token','w') as f:
        f.write(token_text)
        DECtalker.run(token_text)
except discord.errors.LoginFailure:
    print('Login failed. Generate a new token.')
    os.remove('token')