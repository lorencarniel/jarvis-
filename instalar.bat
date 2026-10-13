@echo off
echo ==========================================
echo   J.A.R.V.I.S. - Instalacion Completa
echo ==========================================
echo.

cd /d "%~dp0"

echo Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python no esta instalado!
    echo Descargalo de: https://www.python.org/downloads/
    echo O desde Microsoft Store busca "Python 3.13"
    echo.
    pause
    exit /b 1
)
echo Python encontrado OK

echo.
echo [1/4] Cerrando JARVIS si esta corriendo...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python3.13.exe 2>nul

echo.
echo [2/4] Instalando dependencias de Python...
pip install -r requirements.txt
if errorlevel 1 (
    echo Reintentando con --user...
    pip install --user -r requirements.txt
)

echo.
echo [3/4] Descargando modelo de voz...
if not exist "tts_models" mkdir tts_models
if not exist "tts_models\es_MX-ald-medium.onnx" (
    echo Descargando modelo de voz ~60MB, espera...
    curl -L -o "tts_models\es_MX-ald-medium.onnx" "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx?download=true"
    if exist "tts_models\es_MX-ald-medium.onnx" (
        echo Modelo descargado OK!
    ) else (
        echo No se pudo descargar el modelo, la voz va a funcionar igual con Google TTS.
    )
) else (
    echo Modelo de voz ya existe, saltando...
)

echo.
echo [4/4] Creando carpetas necesarias...
if not exist "ui\downloads" mkdir "ui\downloads"

echo.
echo ==========================================
echo   INSTALACION COMPLETADA!
echo.
echo   Para iniciar: doble click en iniciar.bat
echo ==========================================
echo.
pause
