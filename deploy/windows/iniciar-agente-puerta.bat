@echo off
REM Agente de puerta — PC de ingreso (Windows). Requiere Python 3 instalado.
cd /d "%~dp0agente_puerta"

if not exist "door.env" (
    copy door.env.example door.env
    echo Edita door.env: DOOR_AGENT_SECRET debe coincidir con el VPS.
    notepad door.env
)

if not exist "venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt
)

venv\Scripts\python.exe agent.py
pause
