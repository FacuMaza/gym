#!/usr/bin/env bash
set -euo pipefail
cd /var/www/gym

./venv/bin/pip install -r requirements.txt -q
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py collectstatic --noinput
systemctl restart gym.service

echo "Listo. Puerta: panel web → Puerta → descargar door.local.json en la PC de ingreso."
