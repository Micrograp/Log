"""
main.py — Standalone Telegram Session & Account Management Suite

Provides a unified menu to add new phone accounts, control sessions,
manage worker pools, delete session files, and check SpamBot restrictions.
"""

import os
import sys
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from telethon import TelegramClient

import add_session
from modules import session_manager
from modules import session_login_handler
from scripts import check_sessions
from scripts import deep_check_sessions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

MAIN_MENU = """
============================================================
   📱 TELEGRAM SESSION & ACCOUNT MANAGEMENT SUITE
============================================================

  [1]  ➕ Add / Log in New Telegram Account  (Phone + 2FA + .session)
  [2]  ⚙️  Session Controller & Profile Info (Ping / Profile / Log out)
  [3]  📊 Worker Accounts Dashboard & Pool Manager
  [4]  🗑️  Delete / Remove Session File  (Permanently delete .session)
  [5]  🔍 Quick Session Restriction Check  (Authorization & flags)
  [6]  🔬 Deep SpamBot Restriction Check  (Query @SpamBot for limits)
  [7]  🧹 Clean Expired Sessions  (Bulk delete invalid .session files)
  [0]  Exit

============================================================
"""


async def main():
    while True:
        print(MAIN_MENU)
        choice = input("Choose an option [0-7]: ").strip()

        if choice == "1":
            await add_session.main()
            input("\nPress Enter to return to main menu...")

        elif choice == "2":
            api_id, api_hash, two_fa = add_session.setup_env_credentials()
            await session_manager.control_session_interactive(api_id, api_hash, two_fa)

        elif choice == "3":
            api_id, api_hash, two_fa = add_session.setup_env_credentials()
            await session_manager.run()

        elif choice == "4":
            session_manager.remove_session_file_and_account()
            input("\nPress Enter to return to main menu...")

        elif choice == "5":
            await check_sessions.main()
            input("\nPress Enter to return to main menu...")

        elif choice == "6":
            await deep_check_sessions.main()
            input("\nPress Enter to return to main menu...")

        elif choice == "7":
            api_id, api_hash, two_fa = add_session.setup_env_credentials()
            await session_manager.clean_invalid_sessions(api_id, api_hash)
            input("\nPress Enter to return to main menu...")

        elif choice == "0":
            print("\nGoodbye!")
            break

        else:
            print("\n❌ Invalid choice. Please select [0-7].")


if __name__ == "__main__":
    asyncio.run(main())
