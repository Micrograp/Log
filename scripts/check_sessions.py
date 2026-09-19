"""
check_sessions.py — Quick restriction checker for all session files
"""
import os
import sys
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
ENV_FILE     = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_FILE)

API_ID_RAW   = os.getenv("API_ID", "0")
API_ID       = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0
API_HASH     = os.getenv("API_HASH", "")
TWO_FA       = os.getenv("TWO_FA_PASSWORD", None)


async def check_session(fname: str) -> dict:
    stem  = fname[:-8]
    path  = os.path.join(SESSIONS_DIR, stem)
    result = {
        "file":        fname,
        "stem":        stem,
        "name":        "—",
        "phone":       "—",
        "restricted":  False,
        "reasons":     [],
        "premium":     False,
        "status":      "unknown",
        "error":       None,
    }

    try:
        c = TelegramClient(path, API_ID, API_HASH)
        await c.connect()

        if not await c.is_user_authorized():
            result["status"] = "NOT AUTHORIZED (session expired)"
            await c.disconnect()
            return result

        me = await c.get_me()
        result["name"]  = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown"
        result["phone"] = f"+{me.phone}" if me.phone else stem
        result["premium"] = bool(getattr(me, "premium", False))

        if getattr(me, "restricted", False):
            result["restricted"] = True
            reasons = getattr(me, "restriction_reason", []) or []
            result["reasons"] = [f"{r.platform}: {r.reason} — {r.text}" for r in reasons]

        try:
            full = await c(GetFullUserRequest("me"))
        except Exception:
            pass

        if result["restricted"] or result["reasons"]:
            result["status"] = "🔴 RESTRICTED"
        else:
            result["status"] = "🟢 OK"

        await c.disconnect()

    except Exception as e:
        result["status"] = f"❌ ERROR"
        result["error"]  = str(e)

    return result


async def main():
    if not os.path.exists(SESSIONS_DIR):
        print("No sessions/ folder found.")
        return

    files = [f for f in sorted(os.listdir(SESSIONS_DIR))
             if f.endswith(".session") and not f.endswith("-journal")]

    if not files:
        print("No .session files found in sessions/")
        return

    sep = "═" * 72
    print(f"\n{sep}")
    print(f"  🔍  SESSION RESTRICTION CHECKER  —  {len(files)} session(s)")
    print(sep)

    results = []
    for i, fname in enumerate(files, 1):
        sys.stdout.write(f"  [{i}/{len(files)}]  Checking: {fname[:-8]} ... ")
        sys.stdout.flush()
        r = await check_session(fname)
        results.append(r)
        print(r["status"])

    print(f"\n{sep}")
    print(f"  {'#':>3}  {'Session File':<22} {'Name':<20} {'Phone':<16} Status")
    print("─" * 72)

    ok_count   = 0
    bad_count  = 0

    for i, r in enumerate(results, 1):
        icon = "🟢" if "OK" in r["status"] else "🔴" if "RESTRICT" in r["status"] else "❌"
        print(f"  {i:>3}  {r['stem']:<22} {r['name']:<20} {r['phone']:<16} {icon} {r['status']}")

        if r["reasons"]:
            for reason in r["reasons"]:
                print(f"         ⚠️  Reason: {reason}")
        if r["error"]:
            print(f"         ⚠️  Error: {r['error']}")

        if "OK" in r["status"]:
            ok_count += 1
        else:
            bad_count += 1

    print("─" * 72)
    print(f"  🟢 Clean accounts: {ok_count}")
    print(f"  🔴 Restricted / Error: {bad_count}")
    print(sep)


if __name__ == "__main__":
    asyncio.run(main())
