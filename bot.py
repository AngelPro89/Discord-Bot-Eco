import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands
import requests
from voice import speak_text 
# pyrefly: ignore [missing-import]
from clima import get_weather
import aiohttp    


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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





bot.run(os.getenv("DISCORD_TOKEN"))