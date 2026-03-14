#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-}"
SKIP_INSTALL=0
SKIP_DB_CHECK=0
INIT_DB=1
AUTO_DB_CONTAINER=1

for arg in "$@"; do
  case "$arg" in
    --skip-install)
      SKIP_INSTALL=1
      ;;
    --skip-db-check)
      SKIP_DB_CHECK=1
      ;;
    --no-init-db)
      INIT_DB=0
      ;;
    --no-auto-db-container)
      AUTO_DB_CONTAINER=0
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

init_db_if_needed() {
  python - <<'PY3'
import asyncio
import os
import asyncpg

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'car_booking')

async def exists(dbname: str) -> bool:
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        database=dbname,
        timeout=5,
    )
    await conn.close()
    return True

async def create_if_missing() -> int:
    try:
        await exists(DB_NAME)
        print(f'[OK] Database {DB_NAME!r} is reachable')
        return 0
    except Exception:
        pass

    try:
        admin_conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
            database='postgres',
            timeout=5,
        )
    except Exception as e:
        print(f'[ERROR] Cannot connect to PostgreSQL maintenance DB: {e}')
        return 1

    try:
        present = await admin_conn.fetchval('SELECT 1 FROM pg_database WHERE datname = $1', DB_NAME)
        if not present:
            await admin_conn.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f'[OK] Database {DB_NAME!r} created automatically')
        else:
            print(f'[INFO] Database {DB_NAME!r} already exists')
    except Exception as e:
        print(f'[ERROR] Failed to create/check database {DB_NAME!r}: {e}')
        await admin_conn.close()
        return 1

    await admin_conn.close()

    try:
        await exists(DB_NAME)
        print(f'[OK] Database {DB_NAME!r} is reachable after init')
        return 0
    except Exception as e:
        print(f'[ERROR] Database {DB_NAME!r} still not reachable: {e}')
        return 1

raise SystemExit(asyncio.run(create_if_missing()))
PY3
}

start_local_db_container() {
  local host="${DB_HOST:-127.0.0.1}"
  local port="${DB_PORT:-5432}"
  local user="${DB_USER:-postgres}"
  local pass="${DB_PASS:-postgres}"
  local name="${DB_NAME:-car_booking}"
  local container="${LOCAL_DB_CONTAINER_NAME:-larta-postgres-local}"

  if [[ "$host" != "127.0.0.1" && "$host" != "localhost" ]]; then
    echo "[INFO] DB_HOST is '$host' (not local). Auto docker DB start skipped." >&2
    return 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "[INFO] Docker not found. Cannot auto-start local PostgreSQL container." >&2
    return 1
  fi

  echo "[INFO] Trying to start local PostgreSQL in Docker container '$container'..."

  if docker ps -a --format '{{.Names}}' | grep -Fxq "$container"; then
    docker start "$container" >/dev/null || true
  else
    docker run -d \
      --name "$container" \
      -e POSTGRES_USER="$user" \
      -e POSTGRES_PASSWORD="$pass" \
      -e POSTGRES_DB="$name" \
      -p "$port:5432" \
      postgres:16-alpine >/dev/null
  fi

  # wait up to 30s
  for _ in $(seq 1 30); do
    if check_db >/dev/null 2>&1; then
      echo "[OK] Local PostgreSQL container is ready on $host:$port"
      return 0
    fi
    sleep 1
  done

  echo "[ERROR] Local PostgreSQL container did not become ready in time" >&2
  return 1
}

if [[ "$MODE" != "api" && "$MODE" != "bot" ]]; then
  echo "Usage: $0 [api|bot] [--skip-install] [--skip-db-check] [--no-init-db] [--no-auto-db-container]"
  exit 1
fi

if [[ "$SKIP_DB_CHECK" -eq 0 ]]; then
  if ! check_db; then
    if [[ "$AUTO_DB_CONTAINER" -eq 1 ]]; then
      if start_local_db_container; then
        :
      elif [[ "$INIT_DB" -eq 1 ]]; then
        echo "[INFO] Trying to auto-create database '${DB_NAME:-car_booking}'..."
        if ! init_db_if_needed; then
          echo "[HINT] Check .env values: DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME" >&2
          echo "[HINT] PostgreSQL status: sudo systemctl status postgresql --no-pager" >&2
          echo "[HINT] Start PostgreSQL: sudo systemctl enable --now postgresql" >&2
          echo "[HINT] Create DB manually (if needed): sudo -u postgres psql -c \"CREATE DATABASE ${DB_NAME:-car_booking};\"" >&2
          exit 1
        fi
      else
        echo "[HINT] Check .env values: DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME" >&2
        echo "[HINT] PostgreSQL status: sudo systemctl status postgresql --no-pager" >&2
        echo "[HINT] Start PostgreSQL: sudo systemctl enable --now postgresql" >&2
        exit 1
      fi
    elif [[ "$INIT_DB" -eq 1 ]]; then
      echo "[INFO] Trying to auto-create database '${DB_NAME:-car_booking}'..."
      if ! init_db_if_needed; then
        echo "[HINT] Check .env values: DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME" >&2
        echo "[HINT] PostgreSQL status: sudo systemctl status postgresql --no-pager" >&2
        echo "[HINT] Start PostgreSQL: sudo systemctl enable --now postgresql" >&2
        echo "[HINT] Create DB manually (if needed): sudo -u postgres psql -c \"CREATE DATABASE ${DB_NAME:-car_booking};\"" >&2
        exit 1
      fi
    else
      echo "[HINT] Check .env values: DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME" >&2
      echo "[HINT] PostgreSQL status: sudo systemctl status postgresql --no-pager" >&2
      echo "[HINT] Start PostgreSQL: sudo systemctl enable --now postgresql" >&2
      exit 1
    fi
  fi
else
  echo "[WARN] Skipping DB preflight (--skip-db-check)"
fi

if [[ "$MODE" == "api" ]]; then
  python -m api.start_api
else
  python main.py
fi
