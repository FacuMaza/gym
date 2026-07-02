#!/usr/bin/env bash
# Instalación limpia en Ubuntu — ejecutar como root desde /var/www/gym
set -euo pipefail

APP_DIR="/var/www/gym"
DOMAIN="facugym.sistemgympro.com"

if [[ "$(pwd)" != "$APP_DIR" ]]; then
  echo "Ejecutá desde $APP_DIR (cd $APP_DIR)"
  exit 1
fi

echo "==> Paquetes del sistema"
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip nginx git

echo "==> Carpetas"
mkdir -p logs staticfiles
chmod 775 logs

echo "==> Entorno virtual (nuevo, sin copiar desde PC)"
rm -rf venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

if [[ ! -f venv/bin/gunicorn ]]; then
  echo "ERROR: gunicorn no se instaló"
  exit 1
fi
./venv/bin/gunicorn --version

echo "==> Archivo .env"
if [[ ! -f .env ]]; then
  SECRET=$(./venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
  cat > .env <<EOF
SECRET_KEY=${SECRET}
DEBUG=0
ALLOWED_HOSTS=127.0.0.1
ALLOWED_HOSTS_PARENT=sistemgympro.com
CSRF_TRUSTED_SUBDOMAIN_SUFFIX=sistemgympro.com
PUBLIC_BASE_URL=https://facugym.sistemgympro.com
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=/var/www/gym/box.sqlite3
EOF
else
  echo ".env ya existe, no se sobrescribe"
fi
echo "Puerta Arduino: configurar en el panel web (menú Puerta)."

echo "==> Django"
./venv/bin/python manage.py check
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py collectstatic --noinput

echo "==> systemd"
cp deploy/systemd/gym.socket /etc/systemd/system/gym.socket
cp deploy/systemd/gym.service /etc/systemd/system/gym.service
systemctl daemon-reload
systemctl enable gym.socket gym.service
systemctl reset-failed gym.socket gym.service 2>/dev/null || true
systemctl start gym.socket
systemctl start gym.service

echo "==> Estado del servicio"
systemctl --no-pager status gym.service || true
ls -la /run/gym.sock || true

echo ""
echo "=== Listo la app ==="
echo "Si nginx aún no está configurado para $DOMAIN:"
echo "  cp deploy/nginx/facugym.conf /etc/nginx/sites-available/facugym"
echo "  ln -sf /etc/nginx/sites-available/facugym /etc/nginx/sites-enabled/"
echo "  nginx -t && systemctl reload nginx"
echo "  certbot --nginx -d $DOMAIN"
echo ""
echo "Probar: curl -I --unix-socket /run/gym.sock http://localhost/"
