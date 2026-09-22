import os
from telethon import TelegramClient

try:
    import socks
    HAS_SOCKS = True
except ImportError:
    socks = None
    HAS_SOCKS = False

def get_proxy_config():
    """
    Parses proxy settings from environment variables if set.
    Supports SOCKS5, SOCKS4, HTTP.
    Example env vars:
      PROXY_TYPE=SOCKS5
      PROXY_HOST=127.0.0.1
      PROXY_PORT=1080
      PROXY_USER=username (optional)
      PROXY_PASS=password (optional)
    """
    if not HAS_SOCKS:
        return None

    proxy_host = os.getenv("PROXY_HOST", "").strip()
    proxy_port = os.getenv("PROXY_PORT", "").strip()
    if not proxy_host or not proxy_port:
        return None

    try:
        port = int(proxy_port)
    except ValueError:
        return None

    proxy_type_str = os.getenv("PROXY_TYPE", "SOCKS5").strip().upper()
    type_map = {
        "SOCKS5": getattr(socks, "SOCKS5", 2),
        "SOCKS4": getattr(socks, "SOCKS4", 1),
        "HTTP": getattr(socks, "HTTP", 3),
    }
    proxy_type = type_map.get(proxy_type_str, getattr(socks, "SOCKS5", 2))

    user = os.getenv("PROXY_USER", "").strip() or None
    password = os.getenv("PROXY_PASS", "").strip() or None

    return (proxy_type, proxy_host, port, True, user, password)

def create_telegram_client(session_target, api_id=None, api_hash=None, **kwargs):
    """
    Creates a Telethon TelegramClient instance configured with realistic desktop device headers
    and optional proxy settings to prevent session revocations when hosted on cloud platforms (e.g., Render).
    """
    if not api_id:
        api_id_val = os.getenv("API_ID", "").strip()
        if api_id_val and api_id_val.isdigit():
            api_id = int(api_id_val)
    if not api_hash:
        api_hash = os.getenv("API_HASH", "").strip()

    # Step 3: Realistic device properties
    device_defaults = {
        "device_model": os.getenv("TELEGRAM_DEVICE_MODEL", "Desktop"),
        "system_version": os.getenv("TELEGRAM_SYSTEM_VERSION", "Windows 11 x64"),
        "app_version": os.getenv("TELEGRAM_APP_VERSION", "4.16.2 x64"),
        "lang_code": os.getenv("TELEGRAM_LANG_CODE", "en"),
        "system_lang_code": os.getenv("TELEGRAM_SYSTEM_LANG_CODE", "en"),
    }

    for key, val in device_defaults.items():
        if key not in kwargs:
            kwargs[key] = val

    # Step 4: Proxy configuration
    if "proxy" not in kwargs:
        proxy_config = get_proxy_config()
        if proxy_config:
            kwargs["proxy"] = proxy_config

    return TelegramClient(session_target, api_id, api_hash, **kwargs)
