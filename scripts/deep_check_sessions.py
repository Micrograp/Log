"""
deep_check_sessions.py — Deep restriction check for all session files via @SpamBot & API
"""
import os
import sys
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from telethon import TelegramClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_FILE)

API_ID_RAW = os.getenv("API_ID", "0")
API_ID   = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0
API_HASH = os.getenv("API_HASH", "")

SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")


async def check_session_deep(session_path):
    s_name = os.path.basename(session_path).replace(".session", "")
    client = TelegramClient(session_path, API_ID, API_HASH)

    result = {
        "session": s_name,
        "name": "Unknown",
        "phone": "Unknown",
        "status": "Unknown",
        "spambot_msg": "",
        "can_transfer": False
    }

    try:
        await client.connect()
        if not await client.is_user_authorized():
            result["status"] = "❌ EXPIRED / NOT LOGGED IN"
            await client.disconnect()
            return result

        me = await client.get_me()
        result["name"]  = f"{me.first_name or ''} {me.last_name or ''}".strip()
        result["phone"] = f"+{me.phone}" if me.phone else me.id

        try:
            spambot = await client.get_entity("SpamBot")
            await client.send_message(spambot, "/start")
            await asyncio.sleep(2.0)

            async for msg in client.iter_messages(spambot, limit=1):
                text = msg.text or ""
                result["spambot_msg"] = text.replace("\n", " ")

                if "Good news" in text or "no limits are currently applied" in text or "free as a bird" in text:
                    result["status"] = "🟢 CLEAN (No Restrictions)"
                    result["can_transfer"] = True
                elif "limited" in text or "restricted" in text or "reports" in text:
                    result["status"] = "🔴 SPAM RESTRICTED (Limited by Telegram)"
                    result["can_transfer"] = False
                else:
                    result["status"] = "⚠️ UNKNOWN SPAMBOT RESPONSE"
                    result["can_transfer"] = False
                break
        except Exception as sb_err:
            result["status"] = f"⚠️ Could not query SpamBot: {sb_err}"
            result["can_transfer"] = False

        await client.disconnect()

    except Exception as e:
        result["status"] = f"❌ CONNECTION ERROR: {e}"

    return result


async def main():
    print("\n============================================================")
    print("   🔬 DEEP TELEGRAM ACCOUNT RESTRICTION SCANNER (@SpamBot)")
    print("============================================================")
    print("  Checking all session files against Telegram's official @SpamBot...\n")

    if not os.path.exists(SESSIONS_DIR):
        print(f"❌ Sessions directory not found at: {SESSIONS_DIR}")
        return

    session_files = [
        os.path.join(SESSIONS_DIR, f)
        for f in os.listdir(SESSIONS_DIR)
        if f.endswith(".session") and not f.endswith("-journal.session")
    ]

    if not session_files:
        print("❌ No .session files found.")
        return

    results = []
    for s_file in sorted(session_files):
        print(f"🔄 Checking session: {os.path.basename(s_file)}...")
        res = await check_session_deep(s_file)
        results.append(res)

    print("\n" + "="*80)
    print(f" {'#':<3} {'Session':<18} {'Phone/ID':<16} {'Can Add Members?':<18} {'Status'}")
    print("-" * 80)

    clean_count = 0
    restricted_count = 0

    for idx, r in enumerate(results, 1):
        can_add_str = "✅ YES" if r["can_transfer"] else "❌ NO"
        if r["can_transfer"]:
            clean_count += 1
        else:
            restricted_count += 1

        print(f" {idx:<3} {r['session']:<18} {str(r['phone']):<16} {can_add_str:<18} {r['status']}")
        if r["spambot_msg"]:
            preview = (r["spambot_msg"][:90] + '...') if len(r["spambot_msg"]) > 90 else r["spambot_msg"]
            print(f"     💬 @SpamBot says: \"{preview}\"")

    print("="*80)
    print(f"\n📊 SUMMARY:")
    print(f"  • Total Sessions Checked: {len(results)}")
    print(f"  • 🟢 Clean: {clean_count}")
    print(f"  • 🔴 Restricted: {restricted_count}")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
