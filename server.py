"""
server.py — FastAPI Backend for Telegram Session Creator & Admin Portal

Provides a REST API and Web Dashboard for step-by-step phone login,
OTP verification, 2FA handling, and protected admin session pool management.
"""

import os
import sys
import re
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import date
from typing import Dict, Any, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Body, Header
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    PhoneNumberInvalidError,
    FloodWaitError,
)
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
DATA_DIR = os.path.join(BASE_DIR, "data")
ACCS_FILE = os.path.join(DATA_DIR, "accounts.json")
WEB_DIR = os.path.join(BASE_DIR, "web")
ENV_FILE = os.path.join(BASE_DIR, ".env")

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)

load_dotenv(ENV_FILE)

API_ID_RAW = os.getenv("API_ID", "0")
API_ID = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0
API_HASH = os.getenv("API_HASH", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# ─────────────────────────────────────────────────────────────────────────────
#  Keep-Alive Background Task
#  Pings every registered session every 6 hours to prevent Telegram from
#  revoking idle sessions due to inactivity.
# ─────────────────────────────────────────────────────────────────────────────

KEEPALIVE_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours


async def keepalive_all_sessions():
    """Ping each session with a lightweight get_me() to prevent Telegram from expiring it."""
    api_id, api_hash = get_credentials()
    accounts = load_accounts()
    if not accounts:
        return

    print(f"[KeepAlive] Pinging {len(accounts)} session(s) to prevent expiry...")
    for acc in accounts:
        stem = acc.get("session_file")
        if not stem:
            continue
        sess_path = os.path.join(SESSIONS_DIR, stem)
        if not os.path.exists(f"{sess_path}.session"):
            continue
        try:
            client = TelegramClient(sess_path, api_id, api_hash)
            await client.connect()
            if await client.is_user_authorized():
                await client.get_me()  # lightweight ping
                print(f"[KeepAlive] ✅  {stem}.session — alive")
                if acc.get("status") == "expired":
                    acc["status"] = "active"
            else:
                print(f"[KeepAlive] ❌  {stem}.session — NOT authorized (expired)")
                acc["status"] = "expired"
            await client.disconnect()
        except Exception as e:
            print(f"[KeepAlive] ⚠️  {stem}.session — error: {e}")

    save_accounts(accounts)


async def keepalive_loop():
    """Infinite loop that calls keepalive_all_sessions on startup and every 6 hours."""
    await asyncio.sleep(30)  # small delay after startup before first ping
    while True:
        try:
            await keepalive_all_sessions()
        except Exception as e:
            print(f"[KeepAlive] Loop error: {e}")
        await asyncio.sleep(KEEPALIVE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app_instance):
    task = asyncio.create_task(keepalive_loop())
    print("[KeepAlive] Background keep-alive task started (interval: 6 hours).")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print("[KeepAlive] Background keep-alive task stopped.")


app = FastAPI(title="Telegram Session Admin Portal", lifespan=lifespan)

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# In-memory session tracking for active login attempts
pending_logins: Dict[str, Dict[str, Any]] = {}


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_credentials():
    global API_ID, API_HASH
    load_dotenv(ENV_FILE)
    raw = os.getenv("API_ID", "0")
    api_id = int(raw) if raw.isdigit() else API_ID
    api_hash = os.getenv("API_HASH", API_HASH)
    return api_id, api_hash


def verify_admin_auth(authorization: Optional[str] = Header(None)):
    load_dotenv(ENV_FILE)
    expected_pass = os.getenv("ADMIN_PASSWORD", "admin123")

    if not authorization:
        raise HTTPException(status_code=401, detail="Admin password required.")

    token = authorization.replace("Bearer ", "").strip()
    if token != expected_pass:
        raise HTTPException(status_code=401, detail="Incorrect Admin Password.")


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
        "notes": existing_acc.get("notes", "Logged in via Web Portal") if existing_acc else "Logged in via Web Portal",
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
#  API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

def sync_sessions_with_accounts() -> tuple[list[str], list[dict]]:
    """Auto-register any .session files found in SESSIONS_DIR missing from accounts.json."""
    accounts = load_accounts()
    existing_stems = {a.get("session_file") for a in accounts if a.get("session_file")}

    files = []
    if os.path.exists(SESSIONS_DIR):
        for f in sorted(os.listdir(SESSIONS_DIR)):
            if f.endswith(".session") and not f.endswith("-journal.session"):
                stem = f[:-8]
                files.append(stem)
                if stem not in existing_stems:
                    next_id = max((a.get("id", 0) for a in accounts), default=0) + 1
                    accounts.append({
                        "id": next_id,
                        "label": f"Worker {next_id:02d}",
                        "phone": f"+{stem}",
                        "session_file": stem,
                        "display_name": f"+{stem}",
                        "status": "active",
                        "daily_adds": 0,
                        "daily_limit": 30,
                        "total_adds": 0,
                        "last_active": None,
                        "last_reset_date": date.today().isoformat(),
                        "notes": "Auto-discovered session file",
                    })
                    existing_stems.add(stem)

    # Only save accounts that are newly registered — do NOT delete existing accounts
    # just because their session file isn't detected right now. This prevents accounts
    # from silently disappearing on every page refresh.
    save_accounts(accounts)
    return files, accounts


# ─────────────────────────────────────────────────────────────────────────────
#  API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/admin/sessions")
async def list_sessions_admin(authorization: Optional[str] = Header(None)):
    """Protected API: List all saved session files and worker accounts (Requires Admin Password)."""
    verify_admin_auth(authorization)
    files, accounts = sync_sessions_with_accounts()
    return JSONResponse({
        "session_files": files,
        "accounts": accounts,
        "total": len(files)
    })


@app.post("/api/admin/verify-sessions")
async def verify_sessions_admin(authorization: Optional[str] = Header(None)):
    """Protected API: Live verify Telegram connection, profile info, and status for all sessions."""
    verify_admin_auth(authorization)
    files, accounts = sync_sessions_with_accounts()
    api_id, api_hash = get_credentials()

    updated_accounts = []
    for acc in accounts:
        stem = acc.get("session_file")
        sess_path = os.path.join(SESSIONS_DIR, stem)
        if not os.path.exists(f"{sess_path}.session"):
            acc["status"] = "expired"
            updated_accounts.append(acc)
            continue

        try:
            client = TelegramClient(sess_path, api_id, api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                acc["status"] = "expired"
                acc["notes"] = "Session expired or revoked by Telegram"
            else:
                me = await client.get_me()
                display = f"{me.first_name or ''} {me.last_name or ''}".strip()
                user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"
                acc["display_name"] = f"{display} ({user_tag})" if display else user_tag
                acc["phone"] = f"+{me.phone}" if me.phone else acc.get("phone", f"+{stem}")
                acc["user_id"] = me.id
                acc["username"] = me.username or ""
                acc["is_premium"] = bool(getattr(me, "premium", False))

                if getattr(me, "restricted", False):
                    acc["status"] = "banned"
                elif acc.get("status") in ["expired", "unknown"]:
                    acc["status"] = "active"

            await client.disconnect()
        except Exception as e:
            acc["notes"] = f"Check failed: {str(e)}"

        updated_accounts.append(acc)

    save_accounts(updated_accounts)
    return JSONResponse({
        "success": True,
        "session_files": files,
        "accounts": updated_accounts,
        "total": len(files)
    })


@app.delete("/api/admin/delete-session/{sess_stem}")
async def delete_session_admin(sess_stem: str, authorization: Optional[str] = Header(None)):
    """Protected API: Delete .session file from disk and unregister from database."""
    verify_admin_auth(authorization)
    f1 = os.path.join(SESSIONS_DIR, f"{sess_stem}.session")
    f2 = os.path.join(SESSIONS_DIR, f"{sess_stem}.session-journal")

    deleted_file = False
    try:
        if os.path.exists(f1):
            os.remove(f1)
            deleted_file = True
        if os.path.exists(f2):
            os.remove(f2)
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail="Session file is currently in use by another process (e.g. main.py). Please close any active CLI script before deleting."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not delete file: {str(e)}"
        )

    accounts = load_accounts()
    accounts = [a for a in accounts if a.get("session_file") != sess_stem]
    save_accounts(accounts)

    return JSONResponse({"success": True, "message": f"Deleted session {sess_stem}.session"})


@app.post("/api/admin/set-status/{sess_stem}")
async def set_status_admin(sess_stem: str, payload: dict = Body(...), authorization: Optional[str] = Header(None)):
    """Protected API: Update session account status (active, limited, banned, expired)."""
    verify_admin_auth(authorization)
    new_status = payload.get("status", "active")
    if new_status not in ["active", "limited", "banned", "expired"]:
        raise HTTPException(status_code=400, detail="Invalid status value.")

    accounts = load_accounts()
    found = False
    for a in accounts:
        if a.get("session_file") == sess_stem:
            a["status"] = new_status
            found = True
            break
    
    if not found:
        accounts.append({
            "id": len(accounts) + 1,
            "label": f"Worker {len(accounts)+1:02d}",
            "phone": f"+{sess_stem}",
            "session_file": sess_stem,
            "display_name": f"+{sess_stem}",
            "status": new_status,
            "daily_adds": 0,
            "daily_limit": 30,
            "total_adds": 0,
            "notes": "Updated via Admin Portal"
        })

    save_accounts(accounts)
    return JSONResponse({"success": True, "message": f"Status updated to '{new_status}' for {sess_stem}"})


@app.get("/api/admin/devices/{sess_stem}")
async def get_active_devices_admin(sess_stem: str, authorization: Optional[str] = Header(None)):
    """Protected API: Fetch active Telegram sessions/devices logged into this account."""
    verify_admin_auth(authorization)
    sess_path = os.path.join(SESSIONS_DIR, sess_stem)
    if not os.path.exists(f"{sess_path}.session"):
        raise HTTPException(status_code=404, detail="Session file not found.")

    api_id, api_hash = get_credentials()
    try:
        client = TelegramClient(sess_path, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            accounts = load_accounts()
            for a in accounts:
                if a.get("session_file") == sess_stem:
                    a["status"] = "expired"
            save_accounts(accounts)

            return JSONResponse({
                "success": False,
                "is_authorized": False,
                "session_stem": sess_stem,
                "message": "Session is expired or revoked by Telegram."
            })

        me = await client.get_me()
        user_info = {
            "name": f"{me.first_name or ''} {me.last_name or ''}".strip() or "Telegram User",
            "username": me.username or "",
            "phone": f"+{me.phone}" if me.phone else f"+{sess_stem}",
            "id": me.id,
            "premium": bool(getattr(me, "premium", False)),
            "restricted": bool(getattr(me, "restricted", False)),
        }

        res = await client(GetAuthorizationsRequest())
        await client.disconnect()

        devices = []
        for auth in res.authorizations:
            devices.append({
                "hash": str(auth.hash),
                "device_model": auth.device_model or "Unknown Device",
                "platform": auth.platform or "Unknown Platform",
                "system_version": auth.system_version or "",
                "app_name": auth.app_name or "",
                "app_version": auth.app_version or "",
                "ip": auth.ip or "Unknown",
                "country": auth.country or "Unknown",
                "region": auth.region or "",
                "date_created": auth.date_created.strftime("%Y-%m-%d %H:%M:%S UTC") if auth.date_created else "Unknown",
                "date_active": auth.date_active.strftime("%Y-%m-%d %H:%M:%S UTC") if auth.date_active else "Unknown",
                "current": bool(auth.current),
                "official_app": bool(getattr(auth, "official_app", False)),
            })

        accounts = load_accounts()
        for a in accounts:
            if a.get("session_file") == sess_stem:
                tag = f"@{me.username}" if me.username else f"ID: {me.id}"
                a["display_name"] = f"{user_info['name']} ({tag})"
                a["phone"] = user_info["phone"]
                if a.get("status") == "expired":
                    a["status"] = "active"
        save_accounts(accounts)

        return JSONResponse({
            "success": True,
            "is_authorized": True,
            "session_stem": sess_stem,
            "user": user_info,
            "devices": devices
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch active devices: {str(e)}")


@app.get("/api/admin/otp/{sess_stem}")
async def get_otp_admin(sess_stem: str, authorization: Optional[str] = Header(None)):
    """Protected API: Fetch latest Telegram login/verification code received from Telegram 777000."""
    verify_admin_auth(authorization)
    sess_path = os.path.join(SESSIONS_DIR, sess_stem)
    if not os.path.exists(f"{sess_path}.session"):
        raise HTTPException(status_code=404, detail="Session file not found.")

    api_id, api_hash = get_credentials()
    try:
        client = TelegramClient(sess_path, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            accounts = load_accounts()
            for a in accounts:
                if a.get("session_file") == sess_stem:
                    a["status"] = "expired"
            save_accounts(accounts)
            return JSONResponse({
                "success": False,
                "is_authorized": False,
                "message": "Session is expired or revoked by Telegram."
            })

        messages_data = []
        latest_code = None
        latest_date = None

        try:
            msgs = await client.get_messages(777000, limit=10)
            for m in msgs:
                if not m.text:
                    continue
                codes = re.findall(r'\b(\d{5,6})\b', m.text)
                code = codes[0] if codes else None
                dt_str = m.date.strftime("%Y-%m-%d %H:%M:%S UTC") if m.date else "Unknown"

                if not latest_code and code:
                    latest_code = code
                    latest_date = dt_str

                messages_data.append({
                    "code": code,
                    "text": m.text,
                    "date": dt_str
                })
        except Exception:
            pass

        await client.disconnect()

        return JSONResponse({
            "success": True,
            "is_authorized": True,
            "session_stem": sess_stem,
            "latest_code": latest_code,
            "latest_date": latest_date,
            "messages": messages_data
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read Telegram OTP code: {str(e)}")


@app.post("/api/admin/terminate-device/{sess_stem}")
async def terminate_device_admin(sess_stem: str, payload: dict = Body(...), authorization: Optional[str] = Header(None)):
    """Protected API: Terminate a specific logged-in device session by hash."""
    verify_admin_auth(authorization)
    hash_val = payload.get("hash")
    if hash_val is None or str(hash_val).strip() == "":
        raise HTTPException(status_code=400, detail="Device hash is required.")

    sess_path = os.path.join(SESSIONS_DIR, sess_stem)
    if not os.path.exists(f"{sess_path}.session"):
        raise HTTPException(status_code=404, detail="Session file not found.")

    api_id, api_hash = get_credentials()
    try:
        client = TelegramClient(sess_path, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=401, detail="Session is not authorized.")

        await client(ResetAuthorizationRequest(hash=int(str(hash_val))))
        await client.disconnect()

        return JSONResponse({"success": True, "message": "Device session terminated successfully."})
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "FRESH_RESET_AUTHORISATION_FORBIDDEN" in err_msg or "FreshResetAuthorisationForbidden" in err_msg:
            err_msg = "Telegram restriction: Freshly authorized session cannot terminate existing devices until 24 hours pass."
        elif "HASH_INVALID" in err_msg:
            err_msg = "Invalid device session hash or device was already logged out."
        raise HTTPException(status_code=400, detail=err_msg)


@app.post("/api/admin/change-2fa/{sess_stem}")
async def change_2fa_admin(sess_stem: str, payload: dict = Body(...), authorization: Optional[str] = Header(None)):
    """Protected API: Change 2FA password on Telegram for a session and save previous password history."""
    verify_admin_auth(authorization)

    current_pass = payload.get("current_password", "").strip()
    new_pass = payload.get("new_password", "").strip()
    hint = payload.get("hint", "").strip()

    if not new_pass:
        raise HTTPException(status_code=400, detail="New 2FA password cannot be empty.")

    sess_path = os.path.join(SESSIONS_DIR, sess_stem)
    if not os.path.exists(f"{sess_path}.session"):
        raise HTTPException(status_code=404, detail="Session file not found.")

    accounts = load_accounts()
    target_acc = next((a for a in accounts if a.get("session_file") == sess_stem), None)

    if not current_pass and target_acc and target_acc.get("password"):
        current_pass = target_acc.get("password", "")

    api_id, api_hash = get_credentials()
    try:
        client = TelegramClient(sess_path, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=401, detail="Session is expired or not authorized on Telegram.")

        await client.edit_2fa(
            current_password=current_pass if current_pass else None,
            new_password=new_pass,
            hint=hint
        )
        await client.disconnect()

        old_password = ""
        if target_acc:
            old_password = target_acc.get("password", "")
            prev_list = target_acc.get("previous_passwords", [])
            if old_password and old_password != new_pass and old_password not in prev_list:
                prev_list.insert(0, old_password)
            target_acc["password"] = new_pass
            target_acc["previous_password"] = old_password if old_password else target_acc.get("previous_password", "")
            target_acc["previous_passwords"] = prev_list
            save_accounts(accounts)
        else:
            next_id = max((a.get("id", 0) for a in accounts), default=0) + 1
            target_acc = {
                "id": next_id,
                "label": f"Worker {next_id:02d}",
                "phone": f"+{sess_stem}",
                "session_file": sess_stem,
                "display_name": f"+{sess_stem}",
                "status": "active",
                "daily_adds": 0,
                "daily_limit": 30,
                "total_adds": 0,
                "notes": "Updated password via Admin Portal",
                "password": new_pass,
                "previous_password": "",
                "previous_passwords": []
            }
            accounts.append(target_acc)
            save_accounts(accounts)

        return JSONResponse({
            "success": True,
            "message": f"Successfully updated 2FA password for {sess_stem} on Telegram!",
            "account": target_acc
        })

    except PasswordHashInvalidError:
        raise HTTPException(status_code=400, detail="Current 2FA Password is incorrect.")
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram rate limited this action. Please wait {e.seconds} seconds.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to change 2FA password: {str(e)}")


@app.post("/api/admin/keepalive")
async def manual_keepalive(authorization: Optional[str] = Header(None)):
    """Protected API: Manually trigger a keep-alive ping on all sessions to prevent Telegram from expiring them."""
    verify_admin_auth(authorization)
    try:
        await keepalive_all_sessions()
        accounts = load_accounts()
        return JSONResponse({
            "success": True,
            "message": f"Keep-alive ping sent to {len(accounts)} session(s).",
            "accounts": accounts
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Keep-alive failed: {str(e)}")


@app.get("/api/admin/download/{sess_stem}")
async def download_session_file(sess_stem: str, authorization: Optional[str] = Header(None)):
    """Protected API: Download the raw .session SQLite file for a given account stem."""
    verify_admin_auth(authorization)
    sess_path = os.path.join(SESSIONS_DIR, f"{sess_stem}.session")
    if not os.path.exists(sess_path):
        raise HTTPException(status_code=404, detail=f"Session file '{sess_stem}.session' not found.")
    return FileResponse(
        path=sess_path,
        filename=f"{sess_stem}.session",
        media_type="application/octet-stream"
    )


@app.get("/api/admin/export/json")
async def export_accounts_json(authorization: Optional[str] = Header(None)):
    """Protected API: Export all accounts metadata as a JSON file."""
    verify_admin_auth(authorization)
    accounts = load_accounts()
    return JSONResponse(
        content=accounts,
        headers={"Content-Disposition": "attachment; filename=accounts_export.json"}
    )


PENDING_SESSIONS_DIR = os.path.join(SESSIONS_DIR, "pending")
os.makedirs(PENDING_SESSIONS_DIR, exist_ok=True)


@app.post("/api/send-code")
async def send_code(payload: dict = Body(...)):
    """Step 1: Initiate Telethon connection and send login verification code."""
    phone_input = payload.get("phone", "").strip()
    if not phone_input:
        raise HTTPException(status_code=400, detail="Phone number is required.")

    clean_phone = phone_input.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    sess_stem = clean_phone.replace("+", "").strip()
    final_sess_path = os.path.join(SESSIONS_DIR, sess_stem)
    pending_sess_path = os.path.join(PENDING_SESSIONS_DIR, sess_stem)

    api_id, api_hash = get_credentials()
    if api_id <= 0 or not api_hash:
        raise HTTPException(status_code=500, detail="API_ID or API_HASH missing in server .env configuration.")

    try:
        # Check if already authenticated session exists in SESSIONS_DIR
        if os.path.exists(f"{final_sess_path}.session"):
            client = TelegramClient(final_sess_path, api_id, api_hash)
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                display = f"{me.first_name or ''} {me.last_name or ''}".strip()
                user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"
                register_account_in_db(sess_stem, clean_phone, f"{display} ({user_tag})")
                await client.disconnect()
                return JSONResponse({
                    "already_authorized": True,
                    "message": "Account is already authorized!",
                    "session_file": f"{sess_stem}.session",
                    "user": {"name": display, "username": user_tag, "phone": clean_phone}
                })
            else:
                await client.disconnect()
                # Remove unauthorized file remnant in SESSIONS_DIR
                try:
                    os.remove(f"{final_sess_path}.session")
                except Exception:
                    pass

        # Use PENDING_SESSIONS_DIR for new login attempt
        client = TelegramClient(pending_sess_path, api_id, api_hash)
        await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            display = f"{me.first_name or ''} {me.last_name or ''}".strip()
            user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"
            await client.disconnect()
            
            # Finalize session to SESSIONS_DIR
            if os.path.exists(f"{pending_sess_path}.session"):
                os.replace(f"{pending_sess_path}.session", f"{final_sess_path}.session")
            register_account_in_db(sess_stem, clean_phone, f"{display} ({user_tag})")
            
            return JSONResponse({
                "already_authorized": True,
                "message": "Account is already authorized!",
                "session_file": f"{sess_stem}.session",
                "user": {"name": display, "username": user_tag, "phone": clean_phone}
            })

        sent = await client.send_code_request(clean_phone)
        pending_logins[clean_phone] = {
            "client": client,
            "phone_code_hash": sent.phone_code_hash,
            "sess_stem": sess_stem,
            "pending_sess_path": pending_sess_path,
            "final_sess_path": final_sess_path
        }

        return JSONResponse({
            "success": True,
            "phone": clean_phone,
            "message": "Verification code sent to Telegram app / SMS."
        })

    except PhoneNumberInvalidError:
        raise HTTPException(status_code=400, detail="Invalid phone number format.")
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Rate limited by Telegram. Wait {e.seconds} seconds.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify-code")
async def verify_code(payload: dict = Body(...)):
    """Step 2: Submit OTP verification code."""
    phone_input = payload.get("phone", "").strip()
    code = payload.get("code", "").strip()

    clean_phone = phone_input.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    if clean_phone not in pending_logins:
        raise HTTPException(status_code=400, detail="No active login session found for this phone. Request a new code.")

    item = pending_logins[clean_phone]
    client: TelegramClient = item["client"]
    phone_code_hash = item["phone_code_hash"]
    sess_stem = item["sess_stem"]
    pending_sess_path = item["pending_sess_path"]
    final_sess_path = item["final_sess_path"]

    try:
        await client.sign_in(phone=clean_phone, code=code, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        display = f"{me.first_name or ''} {me.last_name or ''}".strip()
        user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"

        await client.disconnect()
        del pending_logins[clean_phone]

        # Finalize session file only AFTER successful verification
        if os.path.exists(f"{pending_sess_path}.session"):
            os.replace(f"{pending_sess_path}.session", f"{final_sess_path}.session")
        if os.path.exists(f"{pending_sess_path}.session-journal"):
            os.replace(f"{pending_sess_path}.session-journal", f"{final_sess_path}.session-journal")

        register_account_in_db(sess_stem, clean_phone, f"{display} ({user_tag})")

        return JSONResponse({
            "success": True,
            "session_file": f"{sess_stem}.session",
            "user": {"name": display, "username": user_tag, "phone": clean_phone}
        })

    except SessionPasswordNeededError:
        return JSONResponse({"requires_2fa": True, "message": "2-Step Verification password required."})
    except PhoneCodeInvalidError:
        raise HTTPException(status_code=400, detail="Incorrect verification code.")
    except PhoneCodeExpiredError:
        raise HTTPException(status_code=400, detail="Verification code has expired. Request a new code.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify-2fa")
async def verify_2fa(payload: dict = Body(...)):
    """Step 3: Submit 2FA Password if required."""
    phone_input = payload.get("phone", "").strip()
    password = payload.get("password", "").strip()

    clean_phone = phone_input.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    if clean_phone not in pending_logins:
        raise HTTPException(status_code=400, detail="No active login session found for this phone.")

    item = pending_logins[clean_phone]
    client: TelegramClient = item["client"]
    sess_stem = item["sess_stem"]
    pending_sess_path = item["pending_sess_path"]
    final_sess_path = item["final_sess_path"]

    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        display = f"{me.first_name or ''} {me.last_name or ''}".strip()
        user_tag = f"@{me.username}" if me.username else f"ID: {me.id}"

        await client.disconnect()
        del pending_logins[clean_phone]

        # Finalize session file only AFTER successful 2FA verification
        if os.path.exists(f"{pending_sess_path}.session"):
            os.replace(f"{pending_sess_path}.session", f"{final_sess_path}.session")
        if os.path.exists(f"{pending_sess_path}.session-journal"):
            os.replace(f"{pending_sess_path}.session-journal", f"{final_sess_path}.session-journal")

        register_account_in_db(sess_stem, clean_phone, f"{display} ({user_tag})", password=password)

        return JSONResponse({
            "success": True,
            "session_file": f"{sess_stem}.session",
            "user": {"name": display, "username": user_tag, "phone": clean_phone}
        })

    except PasswordHashInvalidError:
        raise HTTPException(status_code=400, detail="Incorrect 2FA Password.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files and page routes
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_file = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Telegram Session Login Portal</h2>")


@app.get("/manage", response_class=HTMLResponse)
async def read_manage():
    manage_file = os.path.join(WEB_DIR, "manage.html")
    if os.path.exists(manage_file):
        with open(manage_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Admin Session Pool Manager</h2>")


if __name__ == "__main__":
    import uvicorn
    print("\nStarting Telegram Session Portal Server at: http://localhost:8000")
    print("Admin Pool Manager available at: http://localhost:8000/manage\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
