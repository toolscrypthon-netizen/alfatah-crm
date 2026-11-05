#!/usr/bin/env bash
# One-shot installer for the Alfatah CRM on an Ubuntu VPS.
#
#   curl -fsSL https://raw.githubusercontent.com/toolscrypthon-netizen/alfatah-crm/main/deploy/install.sh | sudo bash
#
# Safe to run again: it keeps an existing .env and database, pulls the latest
# code and restarts. It refuses to touch the web server if something other
# than Nginx owns ports 80/443, so an existing app is never taken over.
set -euo pipefail

DOMAIN="${CRM_DOMAIN:-office.alfatah-marketing.com}"
REPO="${CRM_REPO:-https://github.com/toolscrypthon-netizen/alfatah-crm.git}"
DIR="${CRM_DIR:-/opt/alfatah-crm}"
CERT_DIR=/etc/ssl/alfatah-crm

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mSTOPPED: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run this as root (or with sudo)."
command -v apt-get >/dev/null || fail "this script is for Ubuntu or Debian."

say "Checking what already uses ports 80 and 443"
web_owners=$(ss -tlnpH '( sport = :80 or sport = :443 )' 2>/dev/null | grep -o 'users:(("[^"]*"' | cut -d'"' -f2 | sort -u | tr '\n' ' ' || true)
echo "In use by: ${web_owners:-nothing}"
for owner in $web_owners; do
  case "$owner" in
    nginx) ;;
    *) ss -tlnp '( sport = :80 or sport = :443 )'
       fail "ports 80/443 belong to '$owner', not Nginx. Nothing was changed. Send this output to Claude." ;;
  esac
done

say "Installing packages (Docker, Nginx, git)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
command -v git >/dev/null || apt-get install -y -qq git
command -v openssl >/dev/null || apt-get install -y -qq openssl
command -v nginx >/dev/null || apt-get install -y -qq nginx
if ! command -v docker >/dev/null; then
  apt-get install -y -qq docker.io || { curl -fsSL https://get.docker.com | sh; }
fi
if ! docker compose version >/dev/null 2>&1; then
  apt-get install -y -qq docker-compose-v2 || apt-get install -y -qq docker-compose-plugin
fi
systemctl enable --now docker >/dev/null
docker compose version

say "Getting the code into $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f .env ]; then
  say "Creating settings (.env) with fresh secrets"
  port=8010
  while ss -tlnH "( sport = :$port )" | grep -q .; do port=$((port + 10)); done
  cp .env.example .env
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(openssl rand -hex 32)|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" .env
  sed -i "s|^INGEST_API_TOKEN=.*|INGEST_API_TOKEN=$(openssl rand -hex 24)|" .env
  sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$DOMAIN|" .env
  sed -i "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN|" .env
  sed -i "s|^CRM_PORT=.*|CRM_PORT=$port|" .env
  chmod 600 .env
else
  say "Keeping the existing .env"
fi
PORT=$(grep '^CRM_PORT=' .env | cut -d= -f2)
echo "The CRM listens privately on 127.0.0.1:$PORT"

say "Building and starting the CRM (first time takes 3-5 minutes)"
docker compose up -d --build
for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $DOMAIN" -H "X-Forwarded-Proto: https" "http://127.0.0.1:$PORT/login/" || true)
  [ "$code" = "200" ] && break
  sleep 3
done
[ "$code" = "200" ] || { docker compose logs web --tail 60; fail "the CRM did not start. Send the lines above to Claude."; }
docker compose exec -T web python manage.py seed_cities

ADMIN_PASSWORD=""
if [ "$(docker compose exec -T web python manage.py shell -c 'from accounts.models import User; print(User.objects.filter(is_superuser=True).exists())' | tr -d '\r')" != "True" ]; then
  say "Creating the owner login"
  ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
  docker compose exec -T -e DJANGO_SUPERUSER_USERNAME=admin -e DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASSWORD" -e DJANGO_SUPERUSER_EMAIL="" \
    web python manage.py createsuperuser --noinput
  docker compose exec -T web python manage.py shell -c \
    "from accounts.models import User; User.objects.filter(username='admin').update(role='admin', first_name='Owner')"
fi

say "Setting up Nginx for $DOMAIN"
if [ ! -f "$CERT_DIR/origin.pem" ]; then
  # Self-signed origin certificate. Cloudflare (SSL mode "Full") encrypts to it;
  # visitors see Cloudflare's own trusted certificate.
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 3650 -subj "/CN=$DOMAIN" \
    -keyout "$CERT_DIR/origin.key" -out "$CERT_DIR/origin.pem" 2>/dev/null
  chmod 600 "$CERT_DIR/origin.key"
fi
if [ -d /etc/nginx/sites-available ]; then
  SITE=/etc/nginx/sites-available/$DOMAIN
else
  SITE=/etc/nginx/conf.d/$DOMAIN.conf
fi
cat > "$SITE" <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate     $CERT_DIR/origin.pem;
    ssl_certificate_key $CERT_DIR/origin.key;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF
[ -d /etc/nginx/sites-enabled ] && ln -sf "$SITE" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t || { rm -f "/etc/nginx/sites-enabled/$DOMAIN"; [ "$SITE" = "/etc/nginx/conf.d/$DOMAIN.conf" ] && rm -f "$SITE"; fail "Nginx rejected the config, so it was removed and Nginx was not reloaded. Send the lines above to Claude."; }
if systemctl is-active --quiet nginx; then systemctl reload nginx; else systemctl enable --now nginx; fi

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  say "Opening web ports in the firewall"
  ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
fi

say "Checking through Nginx"
code=$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/login/" || true)
echo "https://$DOMAIN/login/ answered $code on this server"

printf '\n\033[1;32mDONE. The CRM is running.\033[0m\n'
echo "Address:   https://$DOMAIN"
if [ -n "$ADMIN_PASSWORD" ]; then
  echo "Username:  admin"
  echo "Password:  $ADMIN_PASSWORD   (write it down, then change it after logging in)"
fi
echo "Code and settings: $DIR   (update later with: cd $DIR && git pull && docker compose up -d --build)"
