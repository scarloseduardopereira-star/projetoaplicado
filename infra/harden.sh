#!/usr/bin/env bash
# =============================================================================
# harden.sh — Provisiona e endurece a VM do zero (Ubuntu 26.04 LTS).
#
# Reproduz TODA a infraestrutura da atividade de forma idempotente:
#   SSH só por chave · Fail2Ban (4/24h) · firewall least-privilege ·
#   Nginx + Gunicorn · HTTPS Let's Encrypt (IP + hostname) · PQC · redirect.
#
# Uso (na VM, como usuário com sudo):
#   git clone <REPO_URL> /tmp/app && cd /tmp/app
#   sudo APP_IP=<seu_ip> bash infra/harden.sh
#
# Segredos (SECRET_KEY, hash da senha) são gerados aqui e gravados em
# /opt/app/.env — nunca versionados.
# =============================================================================
set -euo pipefail

# ---- parâmetros (sobrescreva por variável de ambiente) ----------------------
APP_IP="${APP_IP:-163.176.123.133}"
HOSTNAME_SSLIP="${HOSTNAME_SSLIP:-$(echo "$APP_IP" | tr '.' '-').sslip.io}"
REPO_URL="${REPO_URL:-https://github.com/scarloseduardopereira-star/projetoaplicado.git}"
APP_DIR="/opt/app"
APP_USER="appuser"
ADMIN_USER="${ADMIN_USER:-admin}"

echo ">> Provisionando para IP=$APP_IP  hostname=$HOSTNAME_SSLIP"

# ---- 1. pacotes -------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx fail2ban git python3-venv python3-pip snapd iptables-persistent
snap install --classic certbot >/dev/null 2>&1 || true
ln -sf /snap/bin/certbot /usr/bin/certbot

# ---- 2. SSH: desabilita autenticação por senha ------------------------------
install -d -m 755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
EOF
systemctl reload ssh || systemctl reload sshd || true

# ---- 3. Fail2Ban (4 erros -> ban 24h na porta 22) ---------------------------
cp "$(dirname "$0")/fail2ban-jail.local" /etc/fail2ban/jail.local
systemctl enable --now fail2ban
systemctl restart fail2ban

# ---- 4. Firewall least-privilege (só 22/80/443) -----------------------------
iptables -C INPUT -p tcp --dport 80  -j ACCEPT 2>/dev/null || iptables -I INPUT 5 -p tcp --dport 80  -j ACCEPT
iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
netfilter-persistent save >/dev/null 2>&1 || iptables-save >/etc/iptables/rules.v4
# (portas 80/443 também precisam ser liberadas na Security List do provedor)

# ---- 5. Deploy do app -------------------------------------------------------
rm -rf "$APP_DIR"
git clone -q "$REPO_URL" "$APP_DIR"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# .env de produção com segredos gerados na hora (senha pedida no terminal)
if [ ! -f "$APP_DIR/.env" ]; then
  read -rs -p "Defina a senha do usuário '$ADMIN_USER': " APP_PW; echo
  "$APP_DIR/.venv/bin/python" - "$APP_PW" <<PY
import secrets, sys
from argon2 import PasswordHasher
open("$APP_DIR/.env","w").write(
  "APP_ENV=production\n"
  f"SECRET_KEY={secrets.token_hex(32)}\n"
  "APP_USER=$ADMIN_USER\n"
  f"APP_PASSWORD_HASH={PasswordHasher().hash(sys.argv[1])}\n")
PY
fi
id "$APP_USER" >/dev/null 2>&1 || useradd --system --shell /usr/sbin/nologin "$APP_USER"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

# ---- 6. systemd (Gunicorn) --------------------------------------------------
cp "$(dirname "$0")/tccapp.service" /etc/systemd/system/tccapp.service
systemctl daemon-reload
systemctl enable --now tccapp
systemctl restart tccapp

# ---- 7. Nginx (HTTP -> desafio ACME, antes do TLS) --------------------------
mkdir -p /var/www/certbot
cp "$(dirname "$0")/nginx.conf" /etc/nginx/sites-available/tccapp
ln -sf /etc/nginx/sites-available/tccapp /etc/nginx/sites-enabled/tccapp
rm -f /etc/nginx/sites-enabled/default
# durante a 1ª emissão o Nginx ainda não tem os certs; sobe um bloco 80 temporário
if [ ! -d "/etc/letsencrypt/live/$APP_IP" ]; then
  cat >/etc/nginx/sites-available/tccapp-bootstrap <<EOF
server { listen 80 default_server; server_name _;
  location /.well-known/acme-challenge/ { root /var/www/certbot; }
  location / { return 200 'bootstrap'; } }
EOF
  ln -sf /etc/nginx/sites-available/tccapp-bootstrap /etc/nginx/sites-enabled/tccapp
  rm -f /etc/nginx/sites-enabled/tccapp 2>/dev/null || true
  ln -sf /etc/nginx/sites-available/tccapp-bootstrap /etc/nginx/sites-enabled/00-bootstrap
  nginx -t && systemctl reload nginx
fi

# ---- 8. Certificados Let's Encrypt (IP short-lived + hostname) --------------
certbot certonly --webroot -w /var/www/certbot --ip-address "$APP_IP" \
  --non-interactive --agree-tos --register-unsafely-without-email \
  --preferred-profile shortlived || true
certbot certonly --webroot -w /var/www/certbot -d "$HOSTNAME_SSLIP" \
  --non-interactive --agree-tos --register-unsafely-without-email || true

# ---- 9. Sobe o Nginx final (TLS + PQC) e hook de reload na renovação --------
rm -f /etc/nginx/sites-enabled/00-bootstrap
ln -sf /etc/nginx/sites-available/tccapp /etc/nginx/sites-enabled/tccapp
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' >/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
nginx -t && systemctl reload nginx

echo ">> OK. App em https://$APP_IP  |  teste TLS via https://$HOSTNAME_SSLIP"
