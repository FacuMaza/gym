#!/usr/bin/env bash
# Instalar agente de puerta en la PC del kiosco (Linux). Clonar o copiar el repo primero.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/agente_puerta"
cd "$AGENT_DIR"

echo "==> Entorno virtual del agente"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

if [[ ! -f door.env ]]; then
  cp door.env.example door.env
  echo "Editá door.env (DOOR_AGENT_SECRET igual al VPS): nano $AGENT_DIR/door.env"
fi

echo ""
echo "Probar:  cd $AGENT_DIR && ./venv/bin/python agent.py"
echo "Health:  curl -s http://127.0.0.1:8765/health"
echo ""
echo "Servicio systemd (opcional):"
echo "  cp $SCRIPT_DIR/systemd/gym-door-agent.service /etc/systemd/system/"
echo "  systemctl daemon-reload && systemctl enable --now gym-door-agent"
