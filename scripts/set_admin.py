#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from handlers.db.database import Database


async def main() -> int:
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python scripts/set_admin.py <telegram_id> [on|off]")
        return 1

    try:
        telegram_id = int(sys.argv[1])
    except ValueError:
        print("[ERROR] telegram_id must be integer")
        return 1

    mode = (sys.argv[2] if len(sys.argv) > 2 else "on").lower()
    is_admin = mode != "off"

    db = Database()
    await db.create_pool()
    try:
        ok = await db.set_admin_by_telegram_id(telegram_id, is_admin)
        if not ok:
            print("[ERROR] User not found. Ask user to run /start in bot first.")
            return 2

        print(f"[OK] telegram_id={telegram_id} admin={is_admin}")
        return 0
    finally:
        if db.pool:
            await db.pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
