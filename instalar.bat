@echo off
echo ======================================
echo   J.A.R.V.I.S. - Instalacion
echo ======================================
echo.

cd /d "%~dp0"

echo Instalando dependencias de Python...
pip install -r requirements.txt

echo.
echo ======================================
echo   Instalacion completada!
echo   Para iniciar JARVIS ejecuta: iniciar.bat
echo ======================================
pause
