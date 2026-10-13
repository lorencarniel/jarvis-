@echo off
echo ======================================
echo   J.A.R.V.I.S. - Instalacion
echo ======================================
echo.

cd /d "%~dp0"

echo [1/3] Instalando dependencias de Python...
pip install -r requirements.txt

echo.
echo [2/3] Descargando modelo de voz (Piper TTS)...
if not exist "tts_models" mkdir tts_models
if not exist "tts_models\es_MX-ald-medium.onnx" (
    echo Descargando modelo de voz ~60MB...
    curl -L -o "tts_models\es_MX-ald-medium.onnx" "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx?download=true"
    echo Modelo descargado!
) else (
    echo Modelo de voz ya existe, saltando...
)

echo.
echo [3/3] Creando carpetas necesarias...
if not exist "ui\downloads" mkdir "ui\downloads"

echo.
echo ======================================
echo   Instalacion completada!
echo.
echo   Para iniciar JARVIS ejecuta: iniciar.bat
echo   O hace doble click en iniciar_jarvis.vbs
echo ======================================
pause
