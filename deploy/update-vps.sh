#!/usr/bin/env bash
# Actualizar GYM-PRO en VPS después de git pull
set -euo pipefail
cd /var/www/gym

echo "==> Dependencias"
./venv/bin/pip install -r requirements.txt -q

echo "==> Migraciones"
./venv/bin/python manage.py migrate --noinput

echo "==> Estáticos"
./venv/bin/python manage.py collectstatic --noinput

echo "==> Reinicio"
systemctl restart gym.service
systemctl --no-pager status gym.service || true

echo ""
echo "Listo."
if ! grep -q '^DOOR_ARDUINO_ENABLED=1' .env 2>/dev/null; then
  echo "Puerta: agregá al .env del VPS:"
  echo "  DOOR_ARDUINO_ENABLED=1"
  echo "  DOOR_CONTROL_MODE=agent"
  echo "  DOOR_AGENT_URL=http://127.0.0.1:8765"
  echo "  DOOR_AGENT_SECRET=<mismo valor en PC kiosco door.env>"
fi
echo "PC kiosco: deploy/windows/iniciar-agente-puerta.bat o deploy/agente_puerta/agent.py"
