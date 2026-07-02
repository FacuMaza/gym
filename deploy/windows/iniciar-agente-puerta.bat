@echo off
cd /d "%~dp0..\agente_puerta"

if not exist "door.local.json" (
    echo.
    echo  Falta door.local.json
    echo  Descargalo desde el panel web: menu Puerta -^> Descargar door.local.json
    echo  Guardalo en esta carpeta: %cd%
    echo.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Creando entorno...
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt
)

venv\Scripts\python.exe agent.py
pause
