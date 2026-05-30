import sys
sys.stdout.reconfigure(encoding='utf-8')
import pyttsx3  
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wavfile
import speech_recognition as sr
from googletrans import Translator

# Inicializar el motor de voz
engine = pyttsx3.init()

# Configurar parámetros
engine.setProperty('rate', 150)   # Tasa de habla
engine.setProperty('volume', 0.9) # Volumen

# Obtener las voces disponibles
voices = engine.getProperty('voices')


def choose_voice():
    """Pregunta al usuario si quiere voz de hombre o mujer."""
    while True:
        print("\n🗣️ ¿Qué voz prefieres?")
        print("  1 - 👨 Hombre")
        print("  2 - 👩 Mujer")
        choice = input("Elige (1 o 2): ").strip()
        if choice == "1":
            engine.setProperty('voice', voices[0].id)
            print("✅ Voz de hombre seleccionada.")
            break
        elif choice == "2":
            engine.setProperty('voice', voices[1].id)
            print("✅ Voz de mujer seleccionada.")
            break
        else:
            print("❌ Opción inválida. Ingresa 1 o 2.")


def record_audio():
    """Graba audio del micrófono por una duración de 5-10 segundos."""
    # Preguntar al usuario cuántos segundos quiere grabar
    while True:
        try:
            duration = int(input("¿Cuántos segundos quieres grabar? (5-10): "))
            if 5 <= duration <= 10:
                break
            else:
                print("Por favor, ingresa un número entre 5 y 10.")
        except ValueError:
            print("Entrada inválida. Ingresa un número.")

    sample_rate = 44100
    print(f"🎙️ Habla ahora... Tienes {duration} segundos.")
    
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16"
    )
    sd.wait()  # Esperar a que termine la grabación

    wavfile.write("output.wav", sample_rate, recording)
    print("✅ Grabado, pa 😎")


def translate_audio():
    """Transcribe el audio en español y lo traduce al inglés. Retorna el texto traducido."""
    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile("output.wav") as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="es-ES")  # Detecta español
            print(f"📝 Dijiste: {text}")

        # Traducir al inglés
        translator = Translator()
        translated_en = translator.translate(text, dest="en")
        print(f"🌎 Traducción en inglés, pa 😎: {translated_en.text}")
        return translated_en.text

    except sr.UnknownValueError:
        # Si Google no pudo entender el habla debido a ruido o silencio
        print("❌ No se pudo reconocer el habla.")
        return None
    except sr.RequestError as e:
        # Si no hay conexión a Internet o la API no está disponible
        print(f"❌ Error del servicio de reconocimiento: {e}")
        return None
    except Exception as e:
        print(f"❌ Error al traducir: {e}")
        return None


def speak_text(text):
    """Vocaliza el texto traducido en inglés usando pyttsx3."""
    print(f"🔊 Hablando: {text}")
    engine.say(text)
    engine.runAndWait()


def main():
    """Flujo principal: grabar → transcribir → traducir → hablar."""
    print("=" * 50)
    print("  🎤 Traductor de Voz: Español → Inglés 🌎")
    print("=" * 50)

    # Paso 1: Grabar audio en español
    record_audio()

    # Paso 2: Transcribir y traducir a inglés
    translated_text = translate_audio()

    # Paso 3: Elegir voz y vocalizar la traducción en inglés
    if translated_text:
        choose_voice()
        speak_text(translated_text)
    else:
        print("⚠️ No se pudo obtener una traducción para vocalizar.")

    print("\n✅ ¡Proceso completado!")


if __name__ == "__main__":
    main()