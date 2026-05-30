import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

# pyrefly: ignore [missing-import]
import discord
# pyrefly: ignore [missing-import]
from discord.ext import commands
import requests
from voice import speak_text 
# pyrefly: ignore [missing-import]
from clima import get_weather
# pyrefly: ignore [missing-import]
import aiohttp   
import asyncio
from music import extract_tracks, MusicPlayer 


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
players = {}

@bot.event
async def on_ready():
    bot.aio_session = aiohttp.ClientSession()
    print(f'Andamos ready pa 😎👍 {bot.user}')

@bot.event
async def on_close():
    # Cerramos la sesión cuando el bot se apague
    if bot.aio_session:
        await bot.aio_session.close()

@bot.command(name='start')
async def start(ctx):
    await ctx.send('¡Hola! Soy tu bot de confianza, que te dirá si hace un calorazo 🔥🔥🔥 o si te vas a morir de frío🧊🧊❄️❄️ pa 😎👍')

@bot.command(name='weather')
async def weather(ctx, *, city: str):
    # 1. Mensaje de espera interactivo
    waiting_msg = await ctx.send(f"🔍 Buscando el clima para **{city}**...")
    
    # 2. Llamada asíncrona pasando la sesión del bot y la ciudad
    w_info = await get_weather(bot.aio_session, city)
    
    if not w_info:
        await waiting_msg.edit(content="❌ No se pudo obtener el pronóstico. Intenta con otra ciudad.")
        return

    # 3. Procesamos los datos de wttr.in ("Clear +24°C")
    parts = w_info.split('+')
    condition = parts[0].strip() if len(parts) > 0 else "Desconocido"
    temp = parts[1].strip() if len(parts) > 1 else ""

    # 4. Personalización visual dinámica (Emojis y colores según el clima)
    condition_lower = condition.lower()
    color = discord.Color.blue()
    emoji = "🌤️"
    
    if "rain" in condition_lower or "drizzle" in condition_lower:
        emoji = "🌧️"
        color = discord.Color.dark_blue()
    elif "snow" in condition_lower or "ice" in condition_lower:
        emoji = "❄️"
        color = discord.Color.teal()
    elif "clear" in condition_lower or "sun" in condition_lower:
        emoji = "☀️"
        color = discord.Color.gold()
    elif "cloud" in condition_lower or "overcast" in condition_lower:
        emoji = "☁️"
        color = discord.Color.light_grey()

    speak_text(f'En {city} hace {w_info}')

    if ctx.author.avatar:
        author_icon_url = ctx.author.avatar.url
    else:
        # Fallback for users with default avatars (uses their display_avatar or a safe placeholder)
        # Standard default avatar fallback:
        author_icon_url = ctx.author.display_avatar.url 
        # Alternative simple fallback URL if the above also fails (very rare): 
        # author_icon_url = "https://cdn.discordapp.com/embed/avatars/0.png"
    
    # 5. Build the stylized Embed with the fix
    embed = discord.Embed(
        title=f"{emoji} Reporte del Clima para {city.title()}",
        description=f"**En {city.title()} hace {temp}.**",
        color=color
    )
    embed.add_field(name="Temperatura", value=f"{temp}", inline=True)
    embed.add_field(name="Condición", value=f"{condition}", inline=True)
    
    # The FIXED line 77 (highlighted as modified/new code)
    # We use the new, safe author_icon_url variable
    embed.set_footer(text=f"Solicitado por {ctx.author.name}", icon_url=author_icon_url)
    
    # Call the speech function (assumed synchronous, now safe at the end)
    speak_text(f'En {city} hace {w_info}')
    
    # Edit the waiting message to show the final eye-catching embed.
    await waiting_msg.edit(content=None, embed=embed)

class MusicControlView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None) # Los botones no expiran
        self.player = player

    @discord.ui.button(label="⏸️ Pausa / ▶️ Reanudar", style=discord.ButtonStyle.blurple)
    async def pause_resume(self, interaction: discord.Interaction, button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            return await interaction.response.send_message("❌ No estoy en un canal de voz.", ephemeral=True)

        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Música reanudada.", ephemeral=True)
        elif vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Música pausada.", ephemeral=True)
        else:
            await interaction.response.send_message("🔇 No hay nada reproduciéndose en este momento.", ephemeral=True)

    @discord.ui.button(label="⏭️ Saltar", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop() # Al detener el VC, el 'after' del player_loop salta automáticamente a la siguiente
            await interaction.response.send_message("⏭️ Canción saltada.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No hay ninguna canción reproduciéndose.", ephemeral=True)

    @discord.ui.button(label="⏹️ Detener", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button):
        vc = interaction.guild.voice_client
        if vc:
            self.player.queue.clear() # Limpiamos la cola antes de salir
            await vc.disconnect()
            await interaction.response.send_message("⏹️ Reproducción detenida y bot desconectado.", ephemeral=True)
            # Limpiamos el reproductor del diccionario global
            if interaction.guild.id in players:
                del players[interaction.guild.id]
        else:
            await interaction.response.send_message("❌ No estoy conectado a un canal de voz.", ephemeral=True)


# --- COMANDOS DEL BOT ---
@bot.command(name='play')
async def play(ctx, *, search: str):
    # Validar que el usuario esté en un canal de voz
    if not ctx.author.voice:
        return await ctx.send("❌ ¡Debes estar en un canal de voz para usar este comando!")

    # Mensaje de espera (ideal para playlists largas mientras carga la info en segundo plano)
    waiting_msg = await ctx.send("🔍 **Procesando tu petición...** (Si es una playlist esto puede tardar unos segundos)")

    try:
        # FIX: Extraer la info ANTES de conectar al canal de voz
        # Así evitamos conectar y quedarnos sin audio (error 4017)
        tracks = await extract_tracks(search, loop=bot.loop)
        
        if not tracks:
            return await waiting_msg.edit(content="❌ No se encontró ningún resultado o el enlace es privado.")

        # FIX: Conectarse al canal DESPUÉS de confirmar que hay tracks disponibles
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        
        # Pequeña espera para que la conexión de voz se estabilice
        await asyncio.sleep(1)

        # Obtener o crear el reproductor del servidor actual
        if ctx.guild.id not in players:
            players[ctx.guild.id] = MusicPlayer(ctx)
        
        player = players[ctx.guild.id]

        # LÓGICA DE EMBED LLAMATIVO
        embed = discord.Embed(title="🎵 Sistema de Música Avanzado", color=discord.Color.purple())
        
        # Validamos si es una lista de canciones (Playlist) o track único
        if len(tracks) > 1:
            for track in tracks:
                player.queue.append(track)
            
            embed.description = f"✅ Se han añadido **{len(tracks)}** canciones de la Playlist a la lista de espera."
            embed.add_field(name="Origen", value="Lista de reproducción de YouTube", inline=True)
        else:
            player.queue.append(tracks[0])
            embed.description = f"✅ Añadido a la lista de espera:\n**{tracks[0].title}**"
            embed.add_field(name="Canción", value=tracks[0].title, inline=False)

        embed.set_footer(text=f"Solicitado por {ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        # Modificamos el mensaje de espera original por el Embed llamativo y le añadimos los botones interactivos
        await waiting_msg.edit(content=None, embed=embed, view=MusicControlView(player))

    except Exception as e:
        print(f"Error en play: {e}")
        await waiting_msg.edit(content=f"❌ Hubo un error al intentar reproducir el audio: {e}")



bot.run(os.getenv("DISCORD_TOKEN"))