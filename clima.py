   
import aiohttp

async def get_weather(session: aiohttp.ClientSession, city: str) -> str:
    # Reemplazamos espacios por + para que no se rompa la URL
    city_formatted = city.replace(" ", "+")
    base_url = f"https://wttr.in/{city_formatted}?format=%C+%t"
    
    try:
        async with session.get(base_url) as response:
            if response.status == 200:
                text = await response.text()
                return text.strip()
            return None
    except Exception:
        return None
        