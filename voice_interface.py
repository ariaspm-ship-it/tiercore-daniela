import argparse
import os
import sys
from typing import Optional

try:
    import pyaudiowpatch as _pyaudio  # type: ignore
    sys.modules.setdefault("pyaudio", _pyaudio)
except ImportError:
    pass

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None

try:
    import pyttsx3
except ImportError:  # pragma: no cover
    pyttsx3 = None

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:  # pragma: no cover
    speechsdk = None


class DanielaVoice:
    def __init__(
        self,
        mode: str = "offline",
        azure_voice: str = "es-ES-ElviraNeural",
        language: str = "es-ES",
        text_fallback: bool = True,
    ):
        from ai.claude_agent import DanielaAgent

        self.mode = mode
        self.language = language
        self.text_fallback = text_fallback
        self.agent = DanielaAgent()

        self.recognizer = None
        if sr:
            self.recognizer = sr.Recognizer()

        self.tts_engine = None
        self.azure_synthesizer = None

        if self.mode == "azure":
            self._init_azure_tts(azure_voice)
        else:
            self._init_offline_tts()

    def _init_offline_tts(self) -> None:
        if not pyttsx3:
            raise RuntimeError(
                "Falta pyttsx3. Instala dependencias de voz para usar modo offline."
            )

        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty("rate", 150)
        self.tts_engine.setProperty("volume", 0.9)

    def _init_azure_tts(self, azure_voice: str) -> None:
        if not speechsdk:
            raise RuntimeError(
                "Falta azure-cognitiveservices-speech. Instala dependencias de voz para usar modo azure."
            )

        speech_key = os.getenv("AZURE_SPEECH_KEY")
        speech_region = os.getenv("AZURE_SPEECH_REGION")

        if not speech_key or not speech_region:
            raise RuntimeError(
                "Modo azure requiere AZURE_SPEECH_KEY y AZURE_SPEECH_REGION en variables de entorno."
            )

        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        speech_config.speech_synthesis_voice_name = azure_voice
        self.azure_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

    def listen(self) -> Optional[str]:
        if not self.recognizer or not sr:
            return self._listen_fallback("SpeechRecognition no disponible")

        try:
            with sr.Microphone() as source:
                print("\n🎤 Escuchando...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=14)
        except Exception as error:
            return self._listen_fallback(f"Micrófono no disponible ({error})")

        try:
            text = self.recognizer.recognize_google(audio, language=self.language)
            print(f"👤 Tú: {text}")
            return text
        except sr.UnknownValueError:
            print("❌ No te entendí")
            return None
        except Exception as error:
            return self._listen_fallback(f"Error STT ({error})")

    def _listen_fallback(self, reason: str) -> Optional[str]:
        if not self.text_fallback:
            print(f"❌ {reason}")
            return None

        print(f"⚠️ {reason}. Modo texto activado.")
        typed = input("⌨️ Escribe tu consulta (o ENTER para omitir): ").strip()
        if not typed:
            return None
        print(f"👤 Tú: {typed}")
        return typed

    def speak(self, text: str) -> None:
        print(f"🤖 Daniela: {text}")

        if self.mode == "azure" and self.azure_synthesizer:
            self.azure_synthesizer.speak_text_async(text).get()
            return

        if self.tts_engine:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    def run(self) -> None:
        self.speak("Hola, soy Daniela. ¿En qué puedo ayudarte?")

        while True:
            text = self.listen()
            if not text:
                continue

            text_lower = text.lower()
            if "adios" in text_lower or "adiós" in text_lower or "hasta luego" in text_lower:
                self.speak("Hasta luego. Que tengas un buen día.")
                break

            response = self.agent.chat(text)
            self.speak(response)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interfaz de voz para Daniela")
    parser.add_argument("--mode", choices=["offline", "azure"], default="offline")
    parser.add_argument("--language", default="es-ES", help="Idioma STT (Google SpeechRecognition)")
    parser.add_argument("--azure-voice", default="es-ES-ElviraNeural")
    parser.add_argument(
        "--no-text-fallback",
        action="store_true",
        help="Desactiva fallback por teclado si falla el micrófono/STT",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = DanielaVoice(
        mode=args.mode,
        language=args.language,
        azure_voice=args.azure_voice,
        text_fallback=not args.no_text_fallback,
    )
    app.run()


if __name__ == "__main__":
    main()
