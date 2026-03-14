#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-}"
SKIP_INSTALL=0
SKIP_DB_CHECK=0

for arg in "$@"; do
  case "$arg" in
    --skip-install)
      SKIP_INSTALL=1
      ;;
    --skip-db-check)
      SKIP_DB_CHECK=1
      ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "[ERROR] .env not found. Copy .env.example to .env and fill it." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "[INFO] Skipping dependency install (--skip-install)"
fi

# Required runtime directories
mkdir -p photos logs

check_db() {
  python - <<'PY2'
import asyncio
import os
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME'),
            timeout=5,
        )
        await conn.close()
        print('[OK] PostgreSQL connection check passed')
        return 0
    except Exception as e:
        print(f'[ERROR] PostgreSQL connection check failed: {e}')
        return 1

raise SystemExit(asyncio.run(main()))
PY2
}

if [[ "$MODE" != "api" && "$MODE" != "bot" ]]; then
  echo "Usage: $0 [api|bot] [--skip-install] [--skip-db-check]"
  exit 1
fi

if [[ "$SKIP_DB_CHECK" -eq 0 ]]; then
  if ! check_db; then
    echo "[HINT] Check .env values: DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME" >&2
    echo "[HINT] PostgreSQL status: sudo systemctl status postgresql --no-pager" >&2
    echo "[HINT] Start PostgreSQL: sudo systemctl enable --now postgresql" >&2
    echo "[HINT] Create DB if missing: sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME:-car_booking};"" >&2
    exit 1
  fi
else
  echo "[WARN] Skipping DB preflight (--skip-db-check)"
fi

if [[ "$MODE" == "api" ]]; then
  python -m api.start_api
else
  python main.py
fi
