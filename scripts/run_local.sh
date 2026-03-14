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

if [[ "${1:-}" == "api" ]]; then
  python -m api.start_api
elif [[ "${1:-}" == "bot" ]]; then
  python main.py
else
  echo "Usage: $0 [api|bot]"
  exit 1
fi
