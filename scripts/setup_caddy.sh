#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-${APP_DOMAIN:-}}"
BACKEND="${2:-${APP_BACKEND:-127.0.0.1:8000}}"
EMAIL="${3:-${ACME_EMAIL:-}}"

if [[ -z "$DOMAIN" ]]; then
  echo "Usage: sudo ./scripts/setup_caddy.sh <domain> [backend_host:port] [acme_email]"
  echo "Example: sudo ./scripts/setup_caddy.sh journal.kv9.ru 127.0.0.1:8000 admin@kv9.ru"
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "[ERROR] Run as root: sudo ./scripts/setup_caddy.sh ..." >&2
  exit 1
fi

install_caddy() {
  if command -v caddy >/dev/null 2>&1; then
    echo "[OK] Caddy already installed"
    return
  fi

  echo "[INFO] Installing Caddy..."
  apt update
  apt install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg

  install -m 0755 -d /etc/apt/keyrings
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /etc/apt/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null

  apt update
  apt install -y caddy
}

ensure_imports() {
  mkdir -p /etc/caddy/sites

  if [[ ! -f /etc/caddy/Caddyfile ]]; then
    cat > /etc/caddy/Caddyfile <<'EOF'
{
    auto_https on
}

import /etc/caddy/sites/*.caddy
EOF
    return
  fi

  if ! grep -q "import /etc/caddy/sites/\*.caddy" /etc/caddy/Caddyfile; then
    cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%F-%H%M%S)"
    printf "\nimport /etc/caddy/sites/*.caddy\n" >> /etc/caddy/Caddyfile
  fi
}

write_site() {
  local site_file="/etc/caddy/sites/larta-car-booking.caddy"

  {
    if [[ -n "$EMAIL" ]]; then
      cat <<EOF
$DOMAIN {
    tls $EMAIL
    encode zstd gzip

    reverse_proxy $BACKEND

    header {
        Strict-Transport-Security \"max-age=31536000; includeSubDomains; preload\"
        X-Content-Type-Options nosniff
        X-Frame-Options SAMEORIGIN
        Referrer-Policy strict-origin-when-cross-origin
    }
}
EOF
    else
      cat <<EOF
$DOMAIN {
    encode zstd gzip

    reverse_proxy $BACKEND

    header {
        Strict-Transport-Security \"max-age=31536000; includeSubDomains; preload\"
        X-Content-Type-Options nosniff
        X-Frame-Options SAMEORIGIN
        Referrer-Policy strict-origin-when-cross-origin
    }
}
EOF
    fi
  } > "$site_file"

  echo "[OK] Wrote Caddy site config: $site_file"
}

install_caddy
ensure_imports
write_site

caddy validate --config /etc/caddy/Caddyfile
systemctl enable --now caddy
systemctl reload caddy

cat <<EOF

[OK] Caddy is configured.
Domain:  $DOMAIN
Backend: $BACKEND

Caddy will request and auto-renew TLS certs automatically.
Existing certs are reused from:
- /var/lib/caddy/.local/share/caddy
- /var/lib/caddy/.local/state/caddy

Useful checks:
  systemctl status caddy --no-pager
  journalctl -u caddy -n 200 --no-pager
  caddy list-modules | head
EOF
