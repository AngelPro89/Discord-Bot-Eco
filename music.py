import asyncio
# pyrefly: ignore [missing-import]
import discord
import yt_dlp
from collections import deque

# Configuración óptima para streaming de audio sin descargas locales pesadas
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # IMPORTANTE: True rompería las playlists, lo dejamos en False
    'nocheckcertificate': True,
    'ignoreerrors': True, # Para que si una canción de la playlist está borrada, no rompa todo
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    # FIX: Usar archivo de cookies exportado desde el navegador
    # Exporta tus cookies con la extensión "Get cookies.txt LOCALLY" de Chrome/Edge
    'cookiefile': 'cookies.txt',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class TrackInfo:
    """Almacena los metadatos de una canción SIN crear el stream de FFmpeg todavía.
    Esto evita que las URLs expiren antes de que se reproduzcan."""
    def __init__(self, data):
        self.data = data
        self.title = data.get('title', 'Desconocido')
        self.webpage_url = data.get('webpage_url', data.get('url', ''))

    async def create_source(self, loop=None):
        """Re-extrae la URL fresca y crea el FFmpegPCMAudio justo antes de reproducir."""
        loop = loop or asyncio.get_event_loop()
        # Re-extraer para obtener una URL de stream fresca (no expirada)
        fresh_data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(self.webpage_url, download=False)
        )
        if fresh_data is None:
            return None
        
        # Si por alguna razón devuelve entries (no debería para un video individual)
        if 'entries' in fresh_data:
            fresh_data = fresh_data['entries'][0]
        
        source = discord.FFmpegPCMAudio(fresh_data['url'], **FFMPEG_OPTIONS)
        return discord.PCMVolumeTransformer(source, volume=0.5)


async def extract_tracks(url, *, loop=None):
    """Extrae la información de forma asíncrona. Soporta videos individuales y playlists.
    Devuelve una lista de TrackInfo (metadatos), NO streams de audio."""
    loop = loop or asyncio.get_event_loop()
    
    # Extraemos la info sin descargar el archivo
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    
    if data is None:
        return None

    # Si es una playlist, vendrá una lista de canciones en 'entries'
    if 'entries' in data:
        tracks = []
        for entry in data['entries']:
            if entry:  # Asegurar que el video no esté privado o borrado
                tracks.append(TrackInfo(entry))
        return tracks if tracks else None
    
    # Si es una sola canción
    return [TrackInfo(data)]


class MusicPlayer:
    """Manejador de música individual para cada servidor (Guild)"""
    def __init__(self, ctx):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.queue = deque()  # Cola de TrackInfo objects
        self.next = asyncio.Event()
        self.current = None
        self.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Loop infinito que revisa si hay canciones en la cola y las reproduce"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            self.next.clear()
            
            if not self.queue:
                # Si la cola está vacía, espera 1 segundo antes de volver a revisar
                await asyncio.sleep(1)
                continue
            
            # FIX: Verificar que seguimos conectados al canal de voz
            vc = self.guild.voice_client
            if not vc or not vc.is_connected():
                await asyncio.sleep(1)
                continue
            
            track_info = self.queue.popleft()
            self.current = track_info
            
            try:
                # FIX: Crear el stream de audio JUSTO antes de reproducir (URL fresca)
                source = await track_info.create_source(loop=self.bot.loop)
                if source is None:
                    await self.channel.send(f"⚠️ No se pudo reproducir: **{track_info.title}**. Saltando...")
                    continue
                
                await self.channel.send(f"🎶 Ahora reproduciendo: **{track_info.title}**")
                
                # Reproducir audio y activar 'self.next' cuando termine la canción actual
                vc.play(
                    source, 
                    after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
                )
                
                # Esperar hasta que la canción termine o se use el comando skip
                await self.next.wait()
            except Exception as e:
                await self.channel.send(f"⚠️ Error reproduciendo **{track_info.title}**: {e}")
                continue