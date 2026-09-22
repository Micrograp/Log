"""
add_session.py — Interactive Multi-Account Telegram Session Creator

Log in to multiple Telegram accounts via phone numbers and generate
authorized .session files in a continuous loop using Telethon with 2FA support.
"""

import os
import sys
import json
import asyncio
from datetime import date

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from telethon import TelegramClient
from modules.client_factory import create_telegram_client
from telethon.errors import (
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    PhoneNumberInvalidError,
    FloodWaitError,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
DATA_DIR = os.path.join(BASE_DIR, "data")
ACCS_FILE = os.path.join(DATA_DIR, "accounts.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

load_dotenv(ENV_FILE)

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_env_credentials():
    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    two_fa = os.getenv("TWO_FA_PASSWORD", None)

    try:
        api_id = int(api_id_raw) if api_id_raw.isdigit() else 0
    except ValueError:
        api_id = 0

    return api_id, api_hash, two_fa


def setup_env_credentials():
    api_id, api_hash, two_fa = get_env_credentials()

    if api_id > 0 and api_hash:
        return api_id, api_hash, two_fa

    print("============================================================")
    print("   🔑 TELEGRAM API CREDENTIALS REQUIRED")
    print("============================================================")
    print("  To connect to Telegram, you need an API_ID and API_HASH.")
    print("  Get them free from: https://my.telegram.org\n")

    while True:
        raw_id = input("  Enter API_ID (e.g. 12345678): ").strip()
        if raw_id.isdigit() and int(raw_id) > 0:
            api_id = int(raw_id)
            break
        print("  ❌ API_ID must be a valid positive number.")

    while True:
        api_hash = input("  Enter API_HASH (32 character hex string): ").strip()
        if len(api_hash) >= 10:
            break
        print("  ❌ API_HASH cannot be empty.")

    save_env = input("\n  Save credentials to .env file for future logins? (Y/n): ").strip().lower()
    if save_env != "n":
        env_content = f"API_ID={api_id}\nAPI_HASH={api_hash}\n"
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(env_content)
        print("  ✅ Credentials saved to .env")

    return api_id, api_hash, two_fa


def load_accounts() -> list[dict]:
    if os.path.exists(ACCS_FILE):
        try:
            with open(ACCS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_accounts(accounts: list[dict]):
    with open(ACCS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def register_account_in_db(sess_stem: str, phone: str, display: str, password: str = ""):
    accounts = load_accounts()
    existing_acc = next((a for a in accounts if a.get("session_file") == sess_stem), None)
    next_id = existing_acc.get("id") if existing_acc else (max((a.get("id", 0) for a in accounts), default=0) + 1)
    label = existing_acc.get("label") if existing_acc else f"Worker {next_id:02d}"

    current_pass = password if password else (existing_acc.get("password", "") if existing_acc else "")
    prev_passwords = existing_acc.get("previous_passwords", []) if existing_acc else []
    prev_pass = existing_acc.get("previous_password", "") if existing_acc else ""

    accounts = [a for a in accounts if a.get("session_file") != sess_stem]

    new_acc = {
        "id": next_id,
        "label": label,
        "phone": phone,
        "session_file": sess_stem,
        "display_name": display,
        "status": existing_acc.get("status", "active") if existing_acc else "active",
        "daily_adds": existing_acc.get("daily_adds", 0) if existing_acc else 0,
        "daily_limit": existing_acc.get("daily_limit", 30) if existing_acc else 30,
        "total_adds": existing_acc.get("total_adds", 0) if existing_acc else 0,
        "last_active": existing_acc.get("last_active", None) if existing_acc else None,
        "last_reset_date": date.today().isoformat(),
        "notes": existing_acc.get("notes", "") if existing_acc else "",
        "user_id": existing_acc.get("user_id") if existing_acc else None,
        "username": existing_acc.get("username", "") if existing_acc else "",
        "is_premium": existing_acc.get("is_premium", False) if existing_acc else False,
        "password": current_pass,
        "previous_password": prev_pass,
        "previous_passwords": prev_passwords,
    }
    accounts.append(new_acc)
    save_accounts(accounts)


# ─────────────────────────────────────────────────────────────────────────────
#  Single Account Login Routine
# ─────────────────────────────────────────────────────────────────────────────

async def login_single_account(api_id: int, api_hash: str, two_fa_default: str = None):
    print("\n" + "─" * 60)
    print("  📱 LOG IN TELEGRAM ACCOUNT & CREATE .SESSION FILE")
    print("─" * 60)

    default_phone = os.getenv("PHONE_NUMBER", "")
    phone_prompt = f"  Enter Phone Number [{default_phone}]: " if default_phone else "  Enter Phone Number (e.g. +251912345678): "
    phone_input = input(phone_prompt).strip()
    if not phone_input:
        phone_input = default_phone

    if not phone_input:
        print("  ⚠️ Phone number cannot be empty.")
        return False

    clean_phone = phone_input.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    sess_stem = clean_phone.replace("+", "").strip()
    sess_path = os.path.join(SESSIONS_DIR, sess_stem)

    print(f"\n  🔌 Connecting to Telegram for {clean_phone}...")
    client = create_telegram_client(sess_path, api_id, api_hash)

    try:
        await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            display = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Telegram User"
            user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"

            print("\n  ============================================================")
            print("  🟢 ALREADY AUTHORIZED & SESSION FILE READY!")
            print("  ============================================================")
            print(f"  • Name:        {display}")
            print(f"  • User:        {user_tag}")
            print(f"  • Phone:       +{me.phone}")
            print(f"  • Session:     {sess_stem}.session")
            print("  ============================================================")

            register_account_in_db(sess_stem, f"+{me.phone}", f"{display} ({user_tag})")
            await client.disconnect()
            return True

        print(f"  📩 Requesting login code from Telegram for {clean_phone}...")
        try:
            sent_code = await client.send_code_request(clean_phone)
        except PhoneNumberInvalidError:
            print(f"  ❌ Invalid phone number format: {clean_phone}")
            await client.disconnect()
            return False
        except FloodWaitError as e:
            print(f"  ⏳ Telegram rate limit reached. Please wait {e.seconds} seconds before trying again.")
            await client.disconnect()
            return False

        print("  ✅ Verification code sent via Telegram app / SMS.")
        code = input("  💬 Enter the login code you received: ").strip()

        try:
            await client.sign_in(phone=clean_phone, code=code, phone_code_hash=sent_code.phone_code_hash)
        except PhoneCodeInvalidError:
            print("  ❌ Incorrect login code entered.")
            await client.disconnect()
            return False
        except PhoneCodeExpiredError:
            print("  ❌ Login code expired. Please try again.")
            await client.disconnect()
            return False
        except SessionPasswordNeededError:
            print("\n  🔐 2-Step Verification (2FA) is enabled for this account.")
            pwd = two_fa_default
            for attempt in range(1, 4):
                if not pwd:
                    pwd = input(f"  🔑 Enter 2FA Password (attempt {attempt}/3): ").strip()
                try:
                    await client.sign_in(password=pwd)
                    print("  ✅ 2FA password accepted!")
                    break
                except PasswordHashInvalidError:
                    print(f"  ❌ Incorrect 2FA Password (attempt {attempt}/3).")
                    pwd = None
            else:
                print("  ❌ Failed 2FA authentication after 3 attempts.")
                await client.disconnect()
                return False

        me = await client.get_me()
        display = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Telegram User"
        user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"

        print("\n  ============================================================")
        print("  🎉 LOGIN SUCCESSFUL! .SESSION FILE CREATED!")
        print("  ============================================================")
        print(f"  • Account Name: {display}")
        print(f"  • Username/ID:  {user_tag}")
        print(f"  • Phone Number: +{me.phone}")
        print(f"  • Saved File:   sessions/{sess_stem}.session")
        print("  ============================================================")

        register_account_in_db(sess_stem, f"+{me.phone}", f"{display} ({user_tag})")
        await client.disconnect()
        return True

    except Exception as e:
        print(f"  ❌ Login failed: {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Main Continuous Loop Entry Point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("\n============================================================")
    print("   📱 MULTI-ACCOUNT TELEGRAM SESSION CREATOR")
    print("============================================================")
    print("  Create authorized .session files for multiple phone numbers\n")

    api_id, api_hash, two_fa = setup_env_credentials()

    count = 0
    while True:
        success = await login_single_account(api_id, api_hash, two_fa)
        if success:
            count += 1

        again = input("\n  ➕ Add / Log in another Telegram account? (Y/n, default Y): ").strip().lower()
        if again == "n":
            break

    print(f"\n✅ Session creation batch completed. {count} account session(s) processed.")
    print(f"📁 All .session files are stored in: {SESSIONS_DIR}\n")


if __name__ == "__main__":
    asyncio.run(main())
