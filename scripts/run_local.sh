#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[ERROR] .env not found. Copy .env.example to .env and fill it." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Required runtime directories
mkdir -p photos logs

check_db() {
  python - <<'PY'
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
PY
}

if [[ "${1:-}" == "api" ]]; then
  if ! check_db; then
    echo "[HINT] Check DB service and .env values: DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME" >&2
    echo "[HINT] Ubuntu/Debian: sudo systemctl status postgresql" >&2
    exit 1
  fi
  python -m api.start_api
elif [[ "${1:-}" == "bot" ]]; then
  if ! check_db; then
    echo "[HINT] Bot requires DB at startup (create_database + pool)." >&2
    echo "[HINT] Start PostgreSQL and re-run: ./scripts/run_local.sh bot" >&2
    exit 1
  fi
  python main.py
else
  echo "Usage: $0 [api|bot]"
  exit 1
fi
