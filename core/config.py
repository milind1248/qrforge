"""App-wide settings. Override via environment variables or .streamlit/secrets.toml."""
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = __import__("pathlib").Path(os.environ["QRFORGE_DB_PATH"]) if os.environ.get("QRFORGE_DB_PATH") else ROOT / "data" / "qrforge.db"
APP_NAME = "QR Sugi"


def _get(key: str, default: str) -> str:
    """Environment variable first, then Streamlit secrets. Accepts the key at top level (KEY = ...) or inside any
    [section] (e.g. [deploy] license_key = ...), case-insensitively, so a mis-nested secrets file still works."""
    if key in os.environ:
        return os.environ[key]
    try:
        sec = st.secrets
        if key in sec:
            return str(sec[key])
        want = key.lower()
        for k in list(sec.keys()):
            v = sec[k]
            if str(k).lower() == want and not hasattr(v, "keys"):
                return str(v)
            if hasattr(v, "keys"):
                for k2 in v.keys():
                    if str(k2).lower() == want:
                        return str(v[k2])
    except Exception:
        pass
    return default


# Public URL of the deployed app. Dynamic QR codes encode  BASE_URL/?r=<code>
# Local: http://localhost:8501   Streamlit Cloud: https://<your-app>.streamlit.app
BASE_URL = _get("BASE_URL", "http://localhost:8501").rstrip("/")
# Postgres connection string (Supabase). When empty the app uses local SQLite.
DATABASE_URL = _get("DATABASE_URL", "")
# Developer/test switches. They are read ONLY from the real environment (Streamlit copies secrets.toml into os.environ and would
# overwrite an exported DATABASE_URL), so a test run can never reach the production database or send real email.
FORCE_SQLITE = os.environ.get("QRFORGE_FORCE_SQLITE") == "1"
NO_EMAIL = os.environ.get("QRFORGE_NO_EMAIL") == "1"
if FORCE_SQLITE:
    DATABASE_URL = ""
elif os.environ.get("QRFORGE_TEST_PG"):                       # tests on a throwaway LOCAL Postgres only
    from urllib.parse import urlparse as _urlparse
    if _urlparse(os.environ["QRFORGE_TEST_PG"]).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit("QRFORGE_TEST_PG must point at a local database")
    DATABASE_URL = os.environ["QRFORGE_TEST_PG"]
SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_get("SMTP_PORT", "587"))
SMTP_SENDER = _get("SMTP_SENDER", "")
SMTP_PASSWORD = _get("SMTP_PASSWORD", "")
OWNER_EMAIL = _get("OWNER_EMAIL", "")                       # gets admin alerts (new signups / logins)
NOTIFY_USER_LOGIN = _get("NOTIFY_USER_LOGIN", "true").lower() == "true"    # login alert to the user
NOTIFY_OWNER_LOGIN = _get("NOTIFY_OWNER_LOGIN", "true").lower() == "true"  # copy to OWNER_EMAIL
LICENSE_KEY = _get("LICENSE_KEY", "")                    # required: see core/license.py
PAYMENT_PROVIDER = _get("PAYMENT_PROVIDER", "upi_manual")   # upi_manual | mock | razorpay | stripe (later)
CURRENCY = "₹"
