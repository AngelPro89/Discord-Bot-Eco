import sys
sys.stdout.reconfigure(encoding='utf-8')
# pyrefly: ignore [missing-import]
import pyttsx3  
# pyrefly: ignore [missing-import]
import sounddevice as sd
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
import scipy.io.wavfile as wavfile
# pyrefly: ignore [missing-import]
import speech_recognition as sr
# pyrefly: ignore [missing-import]
from googletrans import Translator


def speak_text(text):
    engine = pyttsx3.init()

    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.9)

    print(f"🔊 Hablando: {text}")

    engine.say(text)
    engine.runAndWait()
    engine.stop()


