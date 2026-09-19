"""
session_manager.py — Worker Accounts Dashboard, Session Controller & Remover

Manages multiple Telegram session accounts as a pool of "workers",
tracking daily add limits, total stats, health status, 2FA auth,
session controlling, and permanent file deletion.
"""

import os
import sys
import json
import asyncio
from datetime import date, datetime

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PasswordHashInvalidError,
)

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR      = os.path.join(BASE_DIR, "data")
SESSIONS_DIR  = os.path.join(BASE_DIR, "sessions")
ACCS_FILE     = os.path.join(DATA_DIR, "accounts.json")
ENV_FILE      = os.path.join(BASE_DIR, ".env")

os.makedirs(DATA_DIR,     exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)
load_dotenv(ENV_FILE)

DEFAULT_DAILY_LIMIT = 30   # safe adds per account per day


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def prompt(text: str) -> str:
    sys.stdout.write(text)
    sys.stdout.flush()
    return sys.stdin.readline().rstrip("\r\n")


def today_str() -> str:
    return date.today().isoformat()


def status_icon(status: str) -> str:
    return {
        "active":   "🟢",
        "limited":  "🟡",
        "banned":   "🔴",
        "unknown":  "⚪",
        "error":    "❌",
    }.get(status, "⚪")


# ─────────────────────────────────────────────────────────────────────────────
#  Persistence
# ─────────────────────────────────────────────────────────────────────────────

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


def reset_daily_if_needed(accounts: list[dict]) -> list[dict]:
    """Reset daily_adds counter for any account whose last_reset_date != today."""
    today = today_str()
    changed = False
    for acc in accounts:
        if acc.get("last_reset_date", "") != today:
            acc["daily_adds"]      = 0
            acc["last_reset_date"] = today
            if acc.get("status") == "limited":
                acc["status"] = "active"
            changed = True
    if changed:
        save_accounts(accounts)
    return accounts


def next_id(accounts: list[dict]) -> int:
    if not accounts:
        return 1
    return max(a.get("id", 0) for a in accounts) + 1


def get_all_session_files() -> list[str]:
    """Return all .session file stems in the sessions directory."""
    if not os.path.exists(SESSIONS_DIR):
        return []
    stems = []
    for f in sorted(os.listdir(SESSIONS_DIR)):
        if f.endswith(".session") and not f.endswith("-journal.session"):
            stems.append(f[:-8])
    return stems


# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard display
# ─────────────────────────────────────────────────────────────────────────────

def print_dashboard(accounts: list[dict]):
    accounts = reset_daily_if_needed(accounts)
    all_files = get_all_session_files()
    sep  = "═" * 88
    line = "─" * 88

    print(f"\n{sep}")
    print(f"  📱  WORKER ACCOUNTS DASHBOARD  —  {len(accounts)} account(s) registered ({len(all_files)} .session files)")
    print(f"  🗓️   Date: {today_str()}")
    print(sep)

    if not accounts and not all_files:
        print("  (No accounts registered or session files found. Use option [2] to add accounts.)")
        print(sep)
        return

    print(f"  {'#':>3}  {'Label':<14} {'Phone':<18} {'Status':<13} {'Today':>5} {'Limit':>5} {'Total':>7}  {'Last Active':<16} {'Session File'}")
    print(line)

    total_today  = 0
    total_ever   = 0
    available    = 0

    registered_files = set()
    for acc in accounts:
        idx       = acc.get("id", "?")
        label     = acc.get("label", f"Worker {idx}")[:14]
        phone     = acc.get("phone", "—")[:18]
        status    = acc.get("status", "unknown")
        icon      = status_icon(status)
        daily     = acc.get("daily_adds", 0)
        limit     = acc.get("daily_limit", DEFAULT_DAILY_LIMIT)
        total     = acc.get("total_adds", 0)
        last_act  = acc.get("last_active", "—") or "—"
        sess      = acc.get("session_file", "—")
        registered_files.add(sess)

        total_today += daily
        total_ever  += total
        if status == "active" and daily < limit:
            available += 1

        print(f"  {idx:>3}  {label:<14} {phone:<18} {icon} {status:<10} {daily:>5}/{limit:<4} {total:>7}  {last_act:<16} {sess[:20]}")

    # Unregistered session files
    unregistered = [s for s in all_files if s not in registered_files]
    if unregistered:
        print(line)
        print(f"  ℹ️  Unregistered .session files in sessions/ folder: {', '.join(unregistered)}")

    print(line)
    cap_today = len(accounts) * DEFAULT_DAILY_LIMIT
    print(f"  📊  Today: {total_today} added  |  Capacity: {cap_today}/day  |  Total ever: {total_ever}  |  🟢 Available workers: {available}")
    print(sep)


# ─────────────────────────────────────────────────────────────────────────────
#  Account Operations & 2FA Helper
# ─────────────────────────────────────────────────────────────────────────────

async def add_account_interactive(api_id: int, api_hash: str, two_fa):
    """Interactively log into a new Telegram account with 2FA handling."""
    accounts = load_accounts()
    accounts = reset_daily_if_needed(accounts)

    print("\n" + "─" * 60)
    print("  ➕  ADD NEW WORKER ACCOUNT")
    print("─" * 60)

    phone = prompt("  Phone number (e.g. +251912345678): ").strip()
    if not phone:
        print("  [!] Phone cannot be empty."); return

    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    label = prompt(f"  Label / nickname (e.g. 'Worker {next_id(accounts):02d}'): ").strip()
    if not label:
        label = f"Worker {next_id(accounts):02d}"

    limit_raw = prompt(f"  Daily add limit (default {DEFAULT_DAILY_LIMIT}): ").strip()
    daily_limit = int(limit_raw) if limit_raw.isdigit() and int(limit_raw) > 0 else DEFAULT_DAILY_LIMIT

    sess_name = clean_phone.replace("+", "").strip()
    sess_path = os.path.join(SESSIONS_DIR, sess_name)

    print(f"\n  🔐  Connecting to Telegram: {clean_phone} ...")
    try:
        c = TelegramClient(sess_path, api_id, api_hash)
        await c.connect()

        if not await c.is_user_authorized():
            sent = await c.send_code_request(clean_phone)
            code = prompt("  💬 Enter login code received via Telegram/SMS: ").strip()
            try:
                await c.sign_in(clean_phone, code, phone_code_hash=sent.phone_code_hash)
            except SessionPasswordNeededError:
                print("\n  🔐 2-Step Verification (2FA) is enabled for this account.")
                pwd = two_fa
                for attempt in range(1, 4):
                    if not pwd:
                        pwd = prompt(f"  Enter 2FA Password (attempt {attempt}/3): ").strip()
                    try:
                        await c.sign_in(password=pwd)
                        break
                    except PasswordHashInvalidError:
                        print(f"  ❌ Incorrect 2FA Password (attempt {attempt}/3).")
                        pwd = None
                else:
                    print("  ❌ Failed 2FA authentication after 3 attempts.")
                    await c.disconnect()
                    return

        me      = await c.get_me()
        display = f"{me.first_name or ''} {me.last_name or ''}".strip()
        user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"
        full_display = f"{display} ({user_tag})"
        print(f"  ✅  Logged in as: {full_display}")
        await c.disconnect()

    except Exception as e:
        print(f"  ❌  Could not connect / log in: {e}")
        return

    for a in accounts:
        if a.get("session_file") == sess_name:
            print(f"  ⚠️  Account with session '{sess_name}' is already registered as '{a.get('label')}'.")
            overwrite = prompt("  Overwrite existing entry? (y/N): ").strip().lower()
            if overwrite != "y":
                return
            accounts = [a2 for a2 in accounts if a2.get("session_file") != sess_name]

    new_acc = {
        "id":               next_id(accounts),
        "label":            label,
        "phone":            clean_phone,
        "session_file":     sess_name,
        "display_name":     full_display,
        "status":           "active",
        "daily_adds":       0,
        "daily_limit":      daily_limit,
        "total_adds":       0,
        "last_active":      None,
        "last_reset_date":  today_str(),
        "notes":            "",
    }
    accounts.append(new_acc)
    save_accounts(accounts)
    print(f"\n  ✅  '{label}' registered successfully!  Session: {sess_name}.session")


# ─────────────────────────────────────────────────────────────────────────────
#  Session Removal & Control Features
# ─────────────────────────────────────────────────────────────────────────────

def remove_session_file_and_account():
    """Select a session or account, delete its .session file on disk, and unregister it."""
    accounts = load_accounts()
    all_stems = get_all_session_files()

    if not accounts and not all_stems:
        print("  [!] No session files or registered accounts found.")
        return

    print("\n============================================================")
    print("  🗑️  REMOVE & DELETE TELEGRAM SESSION FILE")
    print("============================================================")

    session_options = []
    seen = set()

    for acc in accounts:
        stem = acc.get("session_file")
        seen.add(stem)
        session_options.append({
            "stem": stem,
            "label": acc.get("label"),
            "phone": acc.get("phone"),
            "id": acc.get("id"),
            "registered": True
        })

    for stem in all_stems:
        if stem not in seen:
            session_options.append({
                "stem": stem,
                "label": "Unregistered",
                "phone": stem,
                "id": None,
                "registered": False
            })

    for idx, opt in enumerate(session_options, 1):
        reg_tag = f"[Acc #{opt['id']}] {opt['label']}" if opt['registered'] else "[Unregistered]"
        print(f"  [{idx}] {reg_tag:<22} Phone/File: {opt['phone']:<18} ({opt['stem']}.session)")

    print("  [0] Cancel")

    raw = prompt("\nSelect session number to DELETE permanently [0-{}]: ".format(len(session_options))).strip()
    if not raw.isdigit() or int(raw) == 0 or int(raw) > len(session_options):
        print("  Cancelled."); return

    selected = session_options[int(raw) - 1]
    stem = selected["stem"]
    sess_file = os.path.join(SESSIONS_DIR, f"{stem}.session")
    journal_file = os.path.join(SESSIONS_DIR, f"{stem}.session-journal")

    confirm = prompt(f"  ⚠️ PERMANENTLY DELETE '{stem}.session' from disk and database? (y/N): ").strip().lower()
    if confirm != "y":
        print("  Cancelled."); return

    deleted_disk = False
    if os.path.exists(sess_file):
        try:
            os.remove(sess_file)
            deleted_disk = True
        except Exception as e:
            print(f"  ❌ Error deleting .session file: {e}")

    if os.path.exists(journal_file):
        try:
            os.remove(journal_file)
        except Exception:
            pass

    if selected["registered"]:
        accounts = [a for a in accounts if a.get("session_file") != stem]
        save_accounts(accounts)

    print(f"\n  ✅ Successfully deleted '{stem}.session' from disk and removed from database.")


async def control_session_interactive(api_id: int, api_hash: str, two_fa: str = None):
    """Detailed controller for individual Telegram session files."""
    accounts = load_accounts()
    all_stems = get_all_session_files()

    if not all_stems:
        print("  [!] No .session files found in sessions/ folder.")
        return

    print("\n============================================================")
    print("  ⚙️   TELEGRAM SESSION CONTROLLER")
    print("============================================================")

    for idx, stem in enumerate(all_stems, 1):
        acc = next((a for a in accounts if a.get("session_file") == stem), None)
        lbl = f"[{acc['label']}]" if acc else "[Unregistered]"
        print(f"  [{idx}] {lbl:<18} Session: {stem}.session")

    print("  [0] Cancel")
    raw = prompt(f"\nSelect session number to control [0-{len(all_stems)}]: ").strip()
    if not raw.isdigit() or int(raw) == 0 or int(raw) > len(all_stems):
        return

    stem = all_stems[int(raw) - 1]
    sess_path = os.path.join(SESSIONS_DIR, stem)
    acc = next((a for a in accounts if a.get("session_file") == stem), None)

    while True:
        print("\n" + "─" * 60)
        print(f"  📱 SESSION CONTROLLER: {stem}.session")
        print("─" * 60)
        print("  [1] 👤 View Account Profile & Status Details")
        print("  [2] 🏥 Health Check & Connection Ping")
        print("  [3] 🚪 Log Out Remote Session (Terminate Telegram Session)")
        print("  [4] 🗑️ Delete Session File from Disk")
        print("  [0] Back")

        ch = prompt("\n  Choose option [0-4]: ").strip()

        if ch == "1":
            print(f"\n  🔍 Fetching profile details for '{stem}.session'...")
            c = TelegramClient(sess_path, api_id, api_hash)
            try:
                await c.connect()
                if not await c.is_user_authorized():
                    print("  ❌ Session is expired or not authorized.")
                else:
                    me = await c.get_me()
                    print("\n  ============================================================")
                    print("  👤 TELEGRAM ACCOUNT PROFILE INFO")
                    print("  ============================================================")
                    print(f"  • User ID:       {me.id}")
                    print(f"  • First Name:    {me.first_name or ''}")
                    print(f"  • Last Name:     {me.last_name or ''}")
                    print(f"  • Username:      @{me.username}" if me.username else "  • Username:      None")
                    print(f"  • Phone:         +{me.phone}" if me.phone else "  • Phone:         Unknown")
                    print(f"  • Premium User:  {'Yes ⭐' if getattr(me, 'premium', False) else 'No'}")
                    print(f"  • Restricted:    {'🔴 YES' if getattr(me, 'restricted', False) else '🟢 Clean'}")
                    print("  ============================================================")
                await c.disconnect()
            except Exception as e:
                print(f"  ❌ Failed to query session: {e}")
            prompt("\n  Press Enter to continue...")

        elif ch == "2":
            print(f"\n  🏥 Pinging session: {stem}...")
            c = TelegramClient(sess_path, api_id, api_hash)
            try:
                await c.connect()
                if await c.is_user_authorized():
                    me = await c.get_me()
                    print(f"  ✅ Connection OK! Authorized as: {me.first_name} (+{me.phone})")
                else:
                    print("  ❌ Session expired / Not authorized.")
                await c.disconnect()
            except Exception as e:
                print(f"  ❌ Connection error: {e}")
            prompt("\n  Press Enter to continue...")

        elif ch == "3":
            confirm = prompt(f"  ⚠️ LOG OUT '{stem}.session' from Telegram servers? (y/N): ").strip().lower()
            if confirm == "y":
                c = TelegramClient(sess_path, api_id, api_hash)
                try:
                    await c.connect()
                    if await c.is_user_authorized():
                        await c.log_out()
                        print("  ✅ Session successfully logged out / revoked from Telegram.")
                    else:
                        print("  ℹ️ Session was already logged out.")
                    await c.disconnect()
                except Exception as e:
                    print(f"  ❌ Failed to log out session: {e}")
            prompt("\n  Press Enter to continue...")

        elif ch == "4":
            confirm = prompt(f"  ⚠️ PERMANENTLY DELETE '{stem}.session' file from disk? (y/N): ").strip().lower()
            if confirm == "y":
                sess_file = os.path.join(SESSIONS_DIR, f"{stem}.session")
                journal_file = os.path.join(SESSIONS_DIR, f"{stem}.session-journal")
                if os.path.exists(sess_file):
                    os.remove(sess_file)
                if os.path.exists(journal_file):
                    os.remove(journal_file)
                if acc:
                    accounts = [a for a in accounts if a.get("session_file") != stem]
                    save_accounts(accounts)
                print(f"  ✅ '{stem}.session' deleted.")
                break

        elif ch == "0":
            break


def edit_account_interactive():
    accounts = load_accounts()
    accounts = reset_daily_if_needed(accounts)
    print_dashboard(accounts)

    if not accounts:
        return

    raw = prompt("\n  Enter account # to edit (or 0 to cancel): ").strip()
    if not raw.isdigit() or int(raw) == 0:
        print("  Cancelled."); return

    target_id = int(raw)
    acc = next((a for a in accounts if a.get("id") == target_id), None)
    if not acc:
        print(f"  [!] No account with ID {target_id}."); return

    print(f"\n  Editing: {acc['label']} ({acc['phone']})")
    print("  Press Enter to keep current value.")

    new_label = prompt(f"  Label [{acc['label']}]: ").strip()
    if new_label:
        acc["label"] = new_label

    new_limit = prompt(f"  Daily limit [{acc['daily_limit']}]: ").strip()
    if new_limit.isdigit() and int(new_limit) > 0:
        acc["daily_limit"] = int(new_limit)

    new_status = prompt(f"  Status [{acc['status']}] (active/limited/banned): ").strip().lower()
    if new_status in ("active", "limited", "banned"):
        acc["status"] = new_status

    new_notes = prompt(f"  Notes [{acc.get('notes', '')}]: ").strip()
    if new_notes:
        acc["notes"] = new_notes

    save_accounts(accounts)
    print(f"  ✅  '{acc['label']}' updated.")


async def check_health_all(api_id: int, api_hash: str):
    """Ping every registered session and update its status."""
    accounts = load_accounts()
    accounts = reset_daily_if_needed(accounts)

    if not accounts:
        print("  [!] No accounts registered."); return

    print(f"\n  🏥  Checking health of {len(accounts)} worker account(s) ...")
    print("─" * 60)

    for acc in accounts:
        sess_path = os.path.join(SESSIONS_DIR, acc["session_file"])
        label     = acc["label"]
        sys.stdout.write(f"  [{acc['id']:>2}] {label:<16} ... ")
        sys.stdout.flush()
        try:
            c = TelegramClient(sess_path, api_id, api_hash)
            await c.connect()
            if await c.is_user_authorized():
                me  = await c.get_me()
                dis = f"{me.first_name or ''} (@{me.username or me.phone or me.id})"
                acc["display_name"] = dis
                if acc["status"] != "banned":
                    acc["status"] = "active" if acc["daily_adds"] < acc["daily_limit"] else "limited"
                print(f"✅  {dis}")
            else:
                acc["status"] = "error"
                print("❌  Not authorized (session expired)")
            await c.disconnect()
        except Exception as e:
            acc["status"] = "error"
            print(f"❌  {e}")

    save_accounts(accounts)
    print("─" * 60)
    print("  ✅  Health check complete.")
    print_dashboard(accounts)


async def clean_invalid_sessions(api_id: int, api_hash: str):
    """Scans sessions/ folder and offers bulk deletion of expired/invalid sessions."""
    stems = get_all_session_files()
    if not stems:
        print("  [!] No .session files found."); return

    print(f"\n  🧹 Scanning {len(stems)} .session file(s) for expired sessions...")
    expired = []

    for stem in stems:
        sess_path = os.path.join(SESSIONS_DIR, stem)
        try:
            c = TelegramClient(sess_path, api_id, api_hash)
            await c.connect()
            auth = await c.is_user_authorized()
            await c.disconnect()
            if not auth:
                expired.append(stem)
        except Exception:
            expired.append(stem)

    if not expired:
        print("  ✅ All .session files are valid and authorized!")
        return

    print(f"\n  ⚠️ Found {len(expired)} expired/invalid session file(s):")
    for s in expired:
        print(f"    • {s}.session")

    confirm = prompt("\n  Delete these expired session files from disk? (y/N): ").strip().lower()
    if confirm == "y":
        for s in expired:
            f1 = os.path.join(SESSIONS_DIR, f"{s}.session")
            f2 = os.path.join(SESSIONS_DIR, f"{s}.session-journal")
            if os.path.exists(f1): os.remove(f1)
            if os.path.exists(f2): os.remove(f2)
        accounts = load_accounts()
        accounts = [a for a in accounts if a.get("session_file") not in expired]
        save_accounts(accounts)
        print(f"  ✅ Deleted {len(expired)} expired session files.")


MENU = """
══════════════════════════════════════════════════════════════════════════════
  📱  WORKER ACCOUNTS & SESSION MANAGER
══════════════════════════════════════════════════════════════════════════════
  [1]  📊  View Dashboard  (all accounts + daily stats)
  [2]  ➕  Add New Worker Account  (login phone number + 2FA support)
  [3]  ⚙️   Session Controller  (profile details / ping / log out session)
  [4]  ✏️   Edit Account Metadata  (label / daily limit / status)
  [5]  🗑️   Delete / Remove Session File  (permanently delete .session)
  [6]  🏥  Check Health All  (ping all sessions, update status)
  [7]  🧹  Clean Expired Sessions  (bulk delete invalid .session files)
  [8]  🔄  Reset Daily Counters  (force reset today's add counts)
  [0]  ← Back
══════════════════════════════════════════════════════════════════════════════"""


async def run(client=None):
    api_id_raw = os.getenv("API_ID", "0")
    api_id   = int(api_id_raw) if api_id_raw.isdigit() else 0
    api_hash = os.getenv("API_HASH",     "")
    two_fa   = os.getenv("TWO_FA_PASSWORD", None)

    while True:
        print(MENU)
        ch = prompt("  Choose [0-8]: ").strip()

        if ch == "1":
            accounts = load_accounts()
            accounts = reset_daily_if_needed(accounts)
            print_dashboard(accounts)
            prompt("\n  Press Enter to continue ...")

        elif ch == "2":
            await add_account_interactive(api_id, api_hash, two_fa)
            prompt("\n  Press Enter to continue ...")

        elif ch == "3":
            await control_session_interactive(api_id, api_hash, two_fa)

        elif ch == "4":
            edit_account_interactive()
            prompt("\n  Press Enter to continue ...")

        elif ch == "5":
            remove_session_file_and_account()
            prompt("\n  Press Enter to continue ...")

        elif ch == "6":
            await check_health_all(api_id, api_hash)
            prompt("\n  Press Enter to continue ...")

        elif ch == "7":
            await clean_invalid_sessions(api_id, api_hash)
            prompt("\n  Press Enter to continue ...")

        elif ch == "8":
            accounts = load_accounts()
            for acc in accounts:
                acc["daily_adds"]      = 0
                acc["last_reset_date"] = today_str()
                if acc.get("status") == "limited":
                    acc["status"] = "active"
            save_accounts(accounts)
            print("  ✅  Daily counters reset for all accounts.")
            prompt("\n  Press Enter to continue ...")

        elif ch == "0":
            break
        else:
            print("  [!] Invalid choice.")
