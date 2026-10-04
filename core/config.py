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
PAYMENT_PROVIDER = _get("PAYMENT_PROVIDER", "mock")   # mock | razorpay | stripe (later)
CURRENCY = "₹"
