# DANIELA · Voice Runbook (Windows)

## 1) Instalar dependencias de voz

```powershell
Set-Location "c:\Users\OliverGonzalez\OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL\Documents\Tier\tiercore-daniela"
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" -m pip install SpeechRecognition pyttsx3 azure-cognitiveservices-speech
```

## 2) Ejecutar modo offline (sin Azure)

```powershell
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" voice_interface.py --mode offline
```

Notas:
- Si no detecta micrófono, activa fallback por teclado automáticamente.
- Para salir, di o escribe: `adiós`.

## 3) Ejecutar modo Azure (voz natural)

```powershell
$env:AZURE_SPEECH_KEY="tu_key"
$env:AZURE_SPEECH_REGION="eastus"
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" voice_interface.py --mode azure --azure-voice es-ES-ElviraNeural
```

## 4) Troubleshooting rápido

- Error de micrófono: revisa permisos de Windows y dispositivo por defecto.
- Error de dependencias: vuelve a ejecutar el `pip install` del paso 1.
- Si quieres forzar solo voz/micrófono (sin fallback por teclado):

```powershell
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" voice_interface.py --mode offline --no-text-fallback
```
