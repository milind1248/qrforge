"""App-wide settings. Override via environment variables or .streamlit/secrets.toml."""
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "qrforge.db"
APP_NAME = "QRForge"


def _get(key: str, default: str) -> str:
    if key in os.environ:
        return os.environ[key]
    try:
        return str(st.secrets[key])
    except Exception:
        return default


# Public URL of the deployed app. Dynamic QR codes encode  BASE_URL/?r=<code>
# Local: http://localhost:8501   Streamlit Cloud: https://<your-app>.streamlit.app
BASE_URL = _get("BASE_URL", "http://localhost:8501").rstrip("/")
# Postgres connection string (Supabase). When empty the app uses local SQLite.
DATABASE_URL = _get("DATABASE_URL", "")
SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_get("SMTP_PORT", "587"))
SMTP_SENDER = _get("SMTP_SENDER", "")
SMTP_PASSWORD = _get("SMTP_PASSWORD", "")
OWNER_EMAIL = _get("OWNER_EMAIL", "")                       # gets admin alerts (new signups / logins)
NOTIFY_USER_LOGIN = _get("NOTIFY_USER_LOGIN", "true").lower() == "true"    # login alert to the user
NOTIFY_OWNER_LOGIN = _get("NOTIFY_OWNER_LOGIN", "true").lower() == "true"  # copy to OWNER_EMAIL
LICENSE_KEY = _get("LICENSE_KEY", "")                    # required: see core/license.py
PAYMENT_PROVIDER = _get("PAYMENT_PROVIDER", "mock")   # mock | razorpay | stripe (later)
CURRENCY = "₹"
