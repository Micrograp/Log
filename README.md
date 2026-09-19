# Telegram Session Creation & Account Management Suite

A complete, clean toolkit to log in to Telegram accounts via CLI or **Web Dashboard**, generate authorized `.session` files in batch, control sessions, manage worker account pools, and handle 2FA passwords & session deletions.

---

## 📂 Project Architecture & Folder Structure

```
login/
├── data/                    # Storage for worker account pool metadata (accounts.json)
├── sessions/                # Storage for generated Telegram .session files
├── modules/                 # Core logic & session handlers
│   ├── __init__.py
│   ├── session_login_handler.py # Session selection & Telethon connection handler
│   └── session_manager.py       # Worker accounts dashboard & session remover
├── scripts/                 # Health check & restriction scanners
│   ├── __init__.py
│   ├── check_sessions.py        # Quick restriction & authorization checker
│   └── deep_check_sessions.py   # Deep @SpamBot restriction checker
├── web/                     # Admin Web Portal UI
│   ├── index.html           # SPA Web Dashboard Layout
│   ├── style.css            # Dark mode glassmorphism theme
│   └── app.js               # Client API integration & step forms
├── .env                     # Local credentials (API_ID, API_HASH, PHONE_NUMBER)
├── .env.example             # Credentials template
├── server.py                # FastAPI Web Dashboard Server
├── add_session.py           # Interactive CLI multi-account creator tool
├── main.py                  # CLI suite main menu
├── requirements.txt         # Dependencies
└── README.md                # Usage guide & documentation
```

---

## 🌐 Running the Admin Web Dashboard (`server.py`)

1. Start the FastAPI Web Server:
   ```bash
   python server.py
   ```
2. Open your web browser and navigate to:  
   👉 **`http://localhost:8000`**

### Web Portal Features:
- **Step 1**: Enter Target Phone Number → Sends login OTP code.
- **Step 2**: Enter Verification Code → Authenticates account.
- **Step 3**: 2FA Password Input (Appears automatically if 2FA is active).
- **Session Pool Dashboard**: Displays all active `.session` files and worker status in real time.

---

## 💻 Running the CLI Suite (`main.py`)

If you prefer using the command line:
```bash
python main.py
```
- **`[1]` Add / Log in New Telegram Account**: Interactive CLI `.session` generator.
- **`[2]` Session Controller & Profile Info**: Ping connection, query profile, or revoke session.
- **`[3]` Worker Accounts Dashboard**: View account pool, daily add limits & stats.
- **`[4]` Delete / Remove Session File**: Permanently delete `.session` file from disk.
- **`[5]` Quick Restriction Check**: Check authorization status.
- **`[6]` Deep SpamBot Restriction Check**: Query official Telegram `@SpamBot`.
- **`[7]` Clean Expired Sessions**: Bulk delete invalid `.session` files.
