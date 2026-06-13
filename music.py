import asyncio
# pyrefly: ignore [missing-import]
import discord
import yt_dlp
from collections import deque

print("YT-DLP VERSION:", yt_dlp.version.__version__)

# Configuración base común optimizada para streaming
YTDL_BASE_OPTIONS = {
    # Cambiado a un selector más flexible para evitar falsos negativos en YT Music
    'format': 'bestaudio/ba/best', 
    'restrictfilenames': True,
    'noplaylist': False,  
    'nocheckcertificate': True,
    'ignoreerrors': True,  # True para que NO falle toda la playlist por un video con error
    'logtostderr': False,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    #'cookiefile': 'cookies.txt',  # Deshabilitado: cookies expiradas causan errores de formato
}

# INSTANCIA 1: Para YouTube Normal (iOS sigue siendo el rey antibloqueos aquí)
YTDL_NORMAL_OPTIONS = YTDL_BASE_OPTIONS.copy()
YTDL_NORMAL_OPTIONS['extractor_args'] = {'youtube': {'player_client': ['ios', 'web']}}
ytdl_normal = yt_dlp.YoutubeDL(YTDL_NORMAL_OPTIONS)

# INSTANCIA 2: Para YouTube Music (android_vr no requiere JS runtime para resolver firmas)
YTDL_MUSIC_OPTIONS = YTDL_BASE_OPTIONS.copy()
YTDL_MUSIC_OPTIONS['extractor_args'] = {'youtube': {'player_client': ['android_vr', 'ios']}}
ytdl_music = yt_dlp.YoutubeDL(YTDL_MUSIC_OPTIONS)


def get_ytdl_client(is_music=False):
    """Devuelve la instancia correcta de yt-dlp según el tipo de contenido"""
    return ytdl_music if is_music else ytdl_normal


FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


class TrackInfo:
    """Almacena los metadatos de una canción SIN crear el stream de FFmpeg todavía."""
    def __init__(self, data, from_music=False):
        self.data = data
        self.title = data.get('title', 'Desconocido')
        url = data.get('url', '')
        self.webpage_url = data.get('webpage_url', url)
        
        print("URL ORIGINAL:", url)
        print("URL REPRODUCCION:", self.webpage_url)
        
        # Guardamos si pertenece a música por si las URLs aplanadas de una playlist cambian de dominio
        self.from_music = from_music or "music.youtube.com" in self.webpage_url

    async def create_source(self, loop=None):
        """Re-extrae la URL fresca usando el cliente adecuado justo antes de reproducir."""
        if not self.webpage_url:
            print("Error: No webpage_url provided.")
            return None
            
        loop = loop or asyncio.get_event_loop()
        client = get_ytdl_client(self.from_music)
        
        fresh_data = await loop.run_in_executor(
            None, lambda: client.extract_info(self.webpage_url, download=False)
        )
        if fresh_data is None:
            print(f"Error obteniendo datos frescos: {self.webpage_url}")
            return None
        
        if 'entries' in fresh_data:
            fresh_data = fresh_data['entries'][0]
        
        source = discord.FFmpegPCMAudio(fresh_data['url'], **FFMPEG_OPTIONS)
        print(f"Reextrayendo: {self.webpage_url}")
        return discord.PCMVolumeTransformer(source, volume=0.5)
        


async def extract_tracks(url, *, loop=None):
    """Extrae la información de forma asíncrona mapeando el cliente correcto."""
    loop = loop or asyncio.get_event_loop()
    
    is_music = "music.youtube.com" in url
    client = get_ytdl_client(is_music)
    
    data = await loop.run_in_executor(None, lambda: client.extract_info(url, download=False))
    
    if data is None:
        return None

    if 'entries' in data:
        tracks = []
        for entry in data['entries']:
            if entry:  
                tracks.append(TrackInfo(entry, from_music=is_music))
        return tracks if tracks else None
    
    return [TrackInfo(data, from_music=is_music)]
    
    print(f"Extrayendo: {url}")


class MusicPlayer:
    """Manejador de música individual para cada servidor (Guild)"""
    def __init__(self, ctx):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.queue = deque()  
        self.next = asyncio.Event()
        self.current = None
        self.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Loop infinito que revisa si hay canciones en la cola y las reproduce"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            self.next.clear()
            
            if not self.queue:
                await asyncio.sleep(1)
                continue
            
            vc = self.guild.voice_client
            if not vc or not vc.is_connected():
                await asyncio.sleep(1)
                continue
            
            track_info = self.queue.popleft()
            self.current = track_info
            
            try:
                source = await track_info.create_source(loop=self.bot.loop)
                if source is None:
                    skip_embed = discord.Embed(
                        description=f"⚠️ No se pudo reproducir: **{track_info.title}**. Saltando...",
                        color=discord.Color.orange()
                    )
                    await self.channel.send(embed=skip_embed)
                    continue
                
                now_playing_embed = discord.Embed(
                    title="🎶 Ahora Reproduciendo",
                    description=f"**{track_info.title}**",
                    color=discord.Color.purple()
                )
                await self.channel.send(embed=now_playing_embed)
                
                vc.play(
                    source, 
                    after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
                )
                
                await self.next.wait()
            except Exception as e:
                error_embed = discord.Embed(
                    description=f"⚠️ Error reproduciendo **{track_info.title}**: `{e}`",
                    color=discord.Color.red()
                )
                await self.channel.send(embed=error_embed)
                continue