@echo off
echo ======================================
echo   Cerrando J.A.R.V.I.S...
echo ======================================
echo.
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python3.13.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq J.A.R.V.I.S.*" 2>nul
echo.
echo JARVIS cerrado. Ya podes borrar la carpeta o actualizar.
echo.
pause
