# pyrefly: ignore [missing-import]
import discord
# pyrefly: ignore [missing-import]
from discord.ui import View, Button
import asyncio
from random import shuffle
# pyrefly: ignore [missing-import]
import speech_recognition as sr
import pyttsx3
import wave
import os
import functools

# pyrefly: ignore [missing-import]
from discord.ext import voice_recv

# --- MONKEY PATCH PARA EVITAR CRASH POR PAQUETES CORRUPTOS (OpusError) ---
import discord.ext.voice_recv.opus as vr_opus
import discord.opus as discord_opus

original_decode_packet = vr_opus.PacketDecoder._decode_packet

def safe_decode_packet(self, packet):
    try:
        return original_decode_packet(self, packet)
    except discord_opus.OpusError as e:
        # Si el paquete está corrupto, lo ignoramos y devolvemos silencio (evita que el bot crashee)
        print(f"⚠️ Paquete de voz corrupto ignorado: {e}")
        return packet, b'\x00' * 3840 # Silencio estándar

vr_opus.PacketDecoder._decode_packet = safe_decode_packet
# -------------------------------------------------------------------------

# ─── Game Settings ───
MAX_LIVES = 3
RECORD_DURATION = 4      # seconds the player has to speak

words_by_difficulty = {
    'Fácil': {
        'gato': 'cat', 'perro': 'dog', 'casa': 'house', 'sol': 'sun',
        'luna': 'moon', 'agua': 'water', 'libro': 'book', 'mesa': 'table',
        'flor': 'flower', 'árbol': 'tree'
    },
    'Intermedio': {
        'computadora': 'computer', 'teléfono': 'phone', 'televisión': 'television',
        'radio': 'radio', 'internet': 'internet', 'biblioteca': 'library',
        'ventana': 'window', 'escalera': 'stairs', 'paraguas': 'umbrella', 'zapato': 'shoe'
    },
    'Difícil': {
        'murciélago': 'bat', 'ornitorrinco': 'platypus', 'dinosaurio': 'dinosaur',
        'hipopótamo': 'hippopotamus', 'rinoceronte': 'rhinoceros', 'mariposa': 'butterfly',
        'relámpago': 'lightning', 'terremoto': 'earthquake', 'cascada': 'waterfall', 'amanecer': 'sunrise'
    },
    'Imposible': {
        'desafortunadamente': 'unfortunately', 'electrocardiograma': 'electrocardiogram',
        'esternocleidomastoideo': 'sternocleidomastoid', 'otorrinolaringólogo': 'otolaryngologist',
        'inconstitucionalidad': 'unconstitutionality', 'paralelepípedo': 'parallelepiped',
        'bioluminiscencia': 'bioluminescence', 'fotosíntesis': 'photosynthesis',
        'onomatopeya': 'onomatopoeia', 'trabalenguas': 'tongue twister'
    }
}

points_per_word = {'Fácil': 1, 'Intermedio': 1, 'Difícil': 1, 'Imposible': 2}
active_games = {} # Guild ID -> Boolean

class UserWaveSink(voice_recv.AudioSink):
    """Sink personalizado que graba los paquetes PCM de un usuario específico a un archivo WAV."""
    def __init__(self, filename, target_user_id):
        super().__init__()
        self.filename = filename
        self.target_user_id = target_user_id
        self.file = wave.open(filename, 'wb')
        self.file.setnchannels(2)
        self.file.setsampwidth(2)
        self.file.setframerate(48000)

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        if user and user.id == self.target_user_id:
            self.file.writeframes(data.pcm)

    def cleanup(self):
        self.file.close()


def generate_tts_file(text, filename):
    """Genera un archivo TTS de forma síncrona."""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.9)
    engine.save_to_file(text, filename)
    engine.runAndWait()
    engine.stop()

def recognize_wav(filename):
    """Reconoce el audio en el archivo WAV usando Google Speech Recognition."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(filename) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="en")
        return text.strip().lower()
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print("SR Error:", e)
        return None
    except Exception as e:
        print("Exception during recognition:", e)
        return None


class DifficultyView(View):
    def __init__(self, target_user, completed_difficulties):
        super().__init__(timeout=60.0)
        self.target_user = target_user
        self.choice = None
        
        difficulties = ['Fácil', 'Intermedio', 'Difícil']
        available = [d for d in difficulties if d not in completed_difficulties]
        
        for diff in available:
            btn = Button(label=diff, style=discord.ButtonStyle.primary)
            # Truco para pasar diff al callback
            btn.callback = functools.partial(self.btn_callback, diff=diff)
            self.add_item(btn)

    async def btn_callback(self, interaction: discord.Interaction, diff: str):
        if interaction.user.id != self.target_user.id:
            return await interaction.response.send_message("❌ Esta partida no es tuya.", ephemeral=True)
        self.choice = diff
        await interaction.response.edit_message(content=f"✅ Seleccionaste: **{diff}**. ¡Prepárate!", view=None)
        self.stop()

async def play_audio_file(vc, bot, filename):
    """Reproduce un archivo de audio local a través del VoiceClient."""
    if not vc.is_connected():
        return
    source = discord.FFmpegPCMAudio(filename)
    source = discord.PCMVolumeTransformer(source, volume=0.8)
    
    # Event para saber cuando termina
    finished = asyncio.Event()
    def after_playing(error):
        bot.loop.call_soon_threadsafe(finished.set)
        
    vc.play(source, after=after_playing)
    await finished.wait()

async def play_game_logic(ctx, vc, bot):
    """Lógica principal del juego en Discord."""
    user = ctx.author
    guild_id = ctx.guild.id
    
    # Mostrar Reglas y Recompensas
    embed = discord.Embed(
        title="🌎 ¡Bienvenido a Magic Translate Game! 🌎",
        description="El juego de traducción por voz definitivo.",
        color=discord.Color.blue()
    )
    embed.add_field(name="📜 Reglas", value="1. Tienes **3 vidas** ❤️❤️❤️\n"
                                          "2. Una palabra en español aparecerá en pantalla.\n"
                                          "3. **Debes decir la traducción en INGLÉS al micrófono de Discord.**\n"
                                          "4. Respuesta correcta = +1 punto 🎉\n"
                                          "5. Respuesta incorrecta = -1 vida 💔", inline=False)
    
    embed.add_field(name="🏆 Títulos (Recompensas)", value="• **Beginner Translator**: Completa la dificultad Fácil.\n"
                                                           "• **Intermediate Linguist**: Completa la dificultad Intermedio.\n"
                                                           "• **Advanced Master**: Completa la dificultad Difícil.\n"
                                                           "• **???**: Hay un título secreto desbloqueable...", inline=False)
    embed.set_footer(text=f"Partida de {user.name}")
    await ctx.send(embed=embed)
    await asyncio.sleep(2)
    
    completed_difficulties = []
    total_score = 0
    lives = MAX_LIVES
    
    tts_filename = f"tts_{guild_id}.wav"
    record_filename = f"rec_{guild_id}.wav"

    while True:
        # Elegir dificultad
        view = DifficultyView(user, completed_difficulties)
        if len(view.children) == 0:
            # Significa que completó las 3 regulares
            break
            
        msg = await ctx.send(embed=discord.Embed(
            title="📚 Selecciona la Dificultad", 
            description="Presiona uno de los botones para comenzar la ronda.",
            color=discord.Color.orange()), view=view)
            
        await view.wait()
        
        if view.choice is None:
            await ctx.send("⏳ Tiempo agotado. Se cancela la partida.")
            return

        diff = view.choice
        word_pairs = words_by_difficulty[diff]
        pts = points_per_word[diff]
        words_list = list(word_pairs.items())
        shuffle(words_list)
        
        await ctx.send(embed=discord.Embed(title=f"🎯 Dificultad: {diff}", description=f"Prepárate, son {len(words_list)} palabras. ¡Cada acierto vale {pts} puntos!", color=discord.Color.green()))
        await asyncio.sleep(2)
        
        round_score = 0
        quit_early = False
        
        for idx, (spanish_word, correct_translation) in enumerate(words_list, start=1):
            if lives <= 0:
                quit_early = True
                break
                
            # Mostrar la palabra
            embed_round = discord.Embed(
                title=f"🔤 Ronda {idx}/{len(words_list)}",
                description=f"Traduce esta palabra al inglés:\n\n✨ **{spanish_word.upper()}** ✨",
                color=discord.Color.purple()
            )
            embed_round.set_footer(text=f"Puntaje actual: {total_score + round_score} | Vidas: {'❤️' * lives}")
            await ctx.send(embed=embed_round)
            
            # Bot avisa: "La cuenta regresiva comienza ahora."
            warning_text = f"Get ready! Translate the word: {spanish_word}."
            await bot.loop.run_in_executor(None, generate_tts_file, warning_text, tts_filename)
            await play_audio_file(vc, bot, tts_filename)
            
            await asyncio.sleep(0.5)
            await ctx.send("🎙️ **¡HABLA AHORA!** Tienes 4 segundos...")
            
            # Iniciar grabación en Discord
            sink = UserWaveSink(record_filename, user.id)
            vc.listen(sink)
            
            await asyncio.sleep(RECORD_DURATION)
            vc.stop_listening()
            await asyncio.sleep(0.5) # Asegurarnos que el archivo cierra bien
            
            # Reconocer voz
            guess = await bot.loop.run_in_executor(None, recognize_wav, record_filename)
            correct = correct_translation.lower()
            
            if not guess:
                lives -= 1
                await ctx.send(embed=discord.Embed(title="❌ ¡No se detectó tu voz o te equivocaste!", description=f"La respuesta correcta era: **{correct_translation}**", color=discord.Color.red()))
            elif guess == correct:
                round_score += pts
                await ctx.send(embed=discord.Embed(title="✅ ¡Correcto!", description=f"Obtuviste +{pts} puntos.", color=discord.Color.green()))
            else:
                lives -= 1
                await ctx.send(embed=discord.Embed(title=f"❌ ¡Incorrecto! Dijiste: '{guess}'", description=f"La respuesta correcta era: **{correct_translation}**", color=discord.Color.red()))
            
            await asyncio.sleep(1)

        total_score += round_score

        if lives <= 0:
            await ctx.send(embed=discord.Embed(title="💀 ¡JUEGO TERMINADO!", description=f"Te quedaste sin vidas. Puntaje final: **{total_score}**", color=discord.Color.dark_red()))
            return

        if not quit_early:
            completed_difficulties.append(diff)
            title_awarded = ""
            if diff == 'Fácil': title_awarded = "Beginner Translator"
            elif diff == 'Intermedio': title_awarded = "Intermediate Linguist"
            elif diff == 'Difícil': title_awarded = "Advanced Master"
            
            await ctx.send(embed=discord.Embed(title=f"🏆 ¡Dificultad {diff} Completada!", description=f"Obtuviste el título: **{title_awarded}**\n\nTu puntaje actual es: **{total_score}**", color=discord.Color.gold()))
            await asyncio.sleep(2)

    # Si completó las 3 dificultades regulares, ofrecer imposible
    if lives > 0:
        embed_imposible = discord.Embed(
            title="🔒 ¡DESAFÍO SECRETO DESBLOQUEADO!",
            description="Has completado todas las dificultades normales. ¿Te atreves al desafío IMPOSIBLE?",
            color=discord.Color.brand_red()
        )
        
        class ImposibleView(View):
            def __init__(self):
                super().__init__(timeout=30)
                self.val = False
            @discord.ui.button(label="🔥 ¡Acepto el desafío!", style=discord.ButtonStyle.danger)
            async def btn_yes(self, interaction: discord.Interaction, btn):
                if interaction.user.id != user.id: return
                self.val = True
                await interaction.response.edit_message(content="¡Que empiece la locura!", view=None)
                self.stop()
            @discord.ui.button(label="🏃 Me retiro con honor", style=discord.ButtonStyle.secondary)
            async def btn_no(self, interaction: discord.Interaction, btn):
                if interaction.user.id != user.id: return
                self.val = False
                await interaction.response.edit_message(content="Te retiras como un campeón.", view=None)
                self.stop()
                
        iview = ImposibleView()
        msg = await ctx.send(embed=embed_imposible, view=iview)
        await iview.wait()
        
        if iview.val:
            words_list = list(words_by_difficulty['Imposible'].items())
            shuffle(words_list)
            pts = points_per_word['Imposible']
            
            await ctx.send(embed=discord.Embed(title="🔥 Dificultad IMPOSIBLE", description=f"¡{len(words_list)} palabras, {pts} puntos cada una!", color=discord.Color.dark_red()))
            await asyncio.sleep(2)
            
            for idx, (spanish_word, correct_translation) in enumerate(words_list, start=1):
                if lives <= 0: break
                
                embed_round = discord.Embed(title=f"🔤 Ronda {idx}/{len(words_list)}", description=f"Traduce:\n\n✨ **{spanish_word.upper()}** ✨", color=discord.Color.purple())
                await ctx.send(embed=embed_round)
                
                warning_text = f"Warning! Translate: {spanish_word}."
                await bot.loop.run_in_executor(None, generate_tts_file, warning_text, tts_filename)
                await play_audio_file(vc, bot, tts_filename)
                
                await ctx.send("🎙️ **¡HABLA AHORA!** Tienes 4 segundos...")
                
                sink = UserWaveSink(record_filename, user.id)
                vc.listen(sink)
                await asyncio.sleep(RECORD_DURATION)
                vc.stop_listening()
                await asyncio.sleep(0.5)
                
                guess = await bot.loop.run_in_executor(None, recognize_wav, record_filename)
                correct = correct_translation.lower()
                
                if not guess or guess != correct:
                    lives -= 1
                    await ctx.send(embed=discord.Embed(title="❌ ¡Incorrecto!", description=f"La respuesta correcta era: **{correct_translation}**", color=discord.Color.red()))
                else:
                    total_score += pts
                    await ctx.send(embed=discord.Embed(title="✅ ¡Impresionante!", description=f"+{pts} puntos.", color=discord.Color.green()))
                await asyncio.sleep(1)
            
            if lives > 0:
                await ctx.send(embed=discord.Embed(
                    title="⚡🔥 TRANSLATION GOD 🔥⚡",
                    description=f"¡Superaste lo imposible!\nPuntaje final: **{total_score}**\n\nHas obtenido el título secreto: **⚡ TRANSLATION GOD ⚡**",
                    color=discord.Color.gold()
                ))
            else:
                await ctx.send(embed=discord.Embed(title="💀 Caíste en la locura", description=f"Puntaje final: **{total_score}**", color=discord.Color.dark_red()))
                
    # Limpieza de archivos si existen
    if os.path.exists(tts_filename): os.remove(tts_filename)
    if os.path.exists(record_filename): os.remove(record_filename)

async def start_discord_game(ctx, bot):
    """Inicia el juego, controla la concurrencia y maneja el VC."""
    guild_id = ctx.guild.id
    
    if active_games.get(guild_id, False):
        await ctx.send("❌ Ya hay un juego ejecutándose en este servidor. Por favor espera a que termine.")
        return
        
    if not ctx.author.voice:
        await ctx.send("❌ Debes estar en un canal de voz para jugar.")
        return
        
    vc = ctx.guild.voice_client
    if vc is None:
        try:
            # IMPORTANTE: Nos conectamos usando VoiceRecvClient para poder escuchar el micrófono
            vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
        except Exception as e:
            await ctx.send(f"❌ Error al conectar al canal de voz: {e}")
            return
    elif not isinstance(vc, voice_recv.VoiceRecvClient):
        # Si estaba conectado normal, reconectar como VoiceRecvClient
        await vc.disconnect()
        vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            
    active_games[guild_id] = True
    try:
        await play_game_logic(ctx, vc, bot)
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió un error inesperado durante el juego: {e}")
        print("Error en juego:", e)
    finally:
        active_games[guild_id] = False
        # Opcional: desconectar el bot al terminar
        # await vc.disconnect()