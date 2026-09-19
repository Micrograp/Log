"""
session_login_handler.py — Session Selection & Telethon Connection Handler

Extracted session selection and authorization logic for Telegram accounts.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
ENV_FILE = os.path.join(BASE_DIR, ".env")

os.makedirs(SESSIONS_DIR, exist_ok=True)
load_dotenv(ENV_FILE)

API_ID_RAW = os.getenv("API_ID", "0")
API_ID = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")
TWO_FA = os.getenv("TWO_FA_PASSWORD", None)


def get_api_credentials():
    global API_ID, API_HASH
    load_dotenv(ENV_FILE)
    api_id_raw = os.getenv("API_ID", "0")
    api_id = int(api_id_raw) if api_id_raw.isdigit() else API_ID
    api_hash = os.getenv("API_HASH", API_HASH)

    if api_id <= 0 or not api_hash:
        print("\n============================================================")
        print("   🔑 TELEGRAM API CREDENTIALS REQUIRED")
        print("============================================================")
        print("  Please enter your API credentials (from https://my.telegram.org)\n")
        while api_id <= 0:
            raw = input("  Enter API_ID: ").strip()
            if raw.isdigit() and int(raw) > 0:
                api_id = int(raw)
        while not api_hash:
            api_hash = input("  Enter API_HASH: ").strip()

        save = input("  Save to .env? (Y/n): ").strip().lower()
        if save != "n":
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(f"API_ID={api_id}\nAPI_HASH={api_hash}\n")

    return api_id, api_hash


def select_session_file(base_dir=None):
    if base_dir is None:
        base_dir = BASE_DIR
    sessions_dir = os.path.join(base_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    saved_sessions = []
    seen = set()
    for fname in sorted(os.listdir(sessions_dir)):
        if fname.endswith(".session") and not fname.endswith("-journal"):
            stem = fname[:-8]
            clean = stem.lstrip("+").strip()
            if clean not in seen:
                seen.add(clean)
                saved_sessions.append(stem)

    if not saved_sessions:
        return os.path.join(sessions_dir, "scanner")

    print("\n============================================================")
    print("   📱 SELECT ACTIVE TELEGRAM ACCOUNT / SESSION")
    print("============================================================")
    session_map = {}
    for idx, s_name in enumerate(saved_sessions, 1):
        print(f"  [{idx}] Session: '{s_name}'")
        session_map[str(idx)] = s_name
    print(f"  [{len(saved_sessions)+1}] + Connect a NEW Telegram Account")

    choice = input(f"\nSelect session [1-{len(saved_sessions)+1}, default 1]: ").strip()
    if choice in session_map:
        selected_stem = session_map[choice]
    elif choice == str(len(saved_sessions)+1):
        new_name = input("Enter phone number for new account (e.g. +251...): ").strip()
        selected_stem = new_name.replace(".session", "").replace("+", "").replace(" ", "_") if new_name else "scanner"
    else:
        selected_stem = saved_sessions[0]

    return os.path.join(sessions_dir, selected_stem)


async def connect_client(session_file, api_id=None, api_hash=None, two_fa=TWO_FA, default_phone=PHONE):
    """Connect to Telegram, silently reusing existing session if already authorized, or prompting for code/2FA."""
    if not api_id or not api_hash:
        api_id, api_hash = get_api_credentials()

    client = TelegramClient(session_file, api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        return client  # Already logged in — no phone prompt needed

    # Not authorized — need to log in fresh
    s_stem = os.path.basename(session_file)
    phone_hint = s_stem if (s_stem.isdigit() or s_stem.startswith("+") or s_stem.lstrip("+").isdigit()) else default_phone
    phone_to_use = phone_hint if phone_hint else input("Enter phone number for this account: ")
    if not phone_to_use.startswith("+") and phone_to_use.isdigit():
        phone_to_use = "+" + phone_to_use

    await client.start(
        phone=lambda: phone_to_use,
        password=lambda: two_fa if two_fa else input("2FA password: ")
    )
    return client
