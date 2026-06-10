# pyrefly: ignore [missing-import]
import discord
import random

ECO_TIPS = [
    {
        "tip": "Apaga las luces al salir.",
        "desc": "Aprovecha la luz natural. No dejes encendidas las luces de habitaciones desocupadas.",
        "emoji": "💡"
    },
    {
        "tip": "Reduce, Reutiliza, Recicla.",
        "desc": "Clasifica tu basura. Dale una segunda vida a los objetos antes de desecharlos.",
        "emoji": "♻️"
    },
    {
        "tip": "Usa bolsas reutilizables.",
        "desc": "Evita el plástico de un solo uso. Lleva siempre contigo una bolsa de tela.",
        "emoji": "🛍️"
    },
    {
        "tip": "Cuida el agua.",
        "desc": "Cierra el grifo mientras te cepillas los dientes o te enjabonas las manos. ¡Cada gota cuenta!",
        "emoji": "💧"
    },
    {
        "tip": "Desconecta tus aparatos.",
        "desc": "Los dispositivos en modo de espera (vampiros energéticos) siguen consumiendo electricidad.",
        "emoji": "🔌"
    },
    {
        "tip": "Planta un árbol o cuida una planta.",
        "desc": "Ayuda a purificar el aire y proporcionar refugio para la vida silvestre local.",
        "emoji": "🌳"
    },
    {
        "tip": "Consume responsablemente.",
        "desc": "Apoya los productos locales y de temporada. Reduce tu huella de carbono.",
        "emoji": "🛒"
    },
    {
        "tip": "Usa transporte sostenible.",
        "desc": "Considera caminar, andar en bicicleta o usar transporte público en lugar del auto.",
        "emoji": "🚲"
    }
]

def get_eco_embed(author_name, author_icon_url):
    item = random.choice(ECO_TIPS)
    
    embed = discord.Embed(
        title=f"{item['emoji']} Tip Ecológico del Día",
        description=f"**{item['tip']}**\n\n{item['desc']}",
        color=0x2ecc71 # Verde esmeralda minimalista
    )
    
    # Thumbnail minimalista (ícono de ecología/planta)
    thumbnail_url = "https://cdn-icons-png.flaticon.com/512/3252/3252654.png"
    embed.set_thumbnail(url=thumbnail_url)
    
    embed.add_field(name="Impacto Positivo", value="🌿 Pequeñas acciones sumadas generan un gran cambio en el planeta.", inline=False)
    
    embed.set_footer(text=f"Solicitado por {author_name}", icon_url=author_icon_url)
    
    return embed
