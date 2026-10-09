"""Site counters for the sidebar: visits, QR codes created, and the creators leaderboard. Counters live in the existing `settings` table."""
from datetime import datetime, timezone

import streamlit as st

from core import db


def _bump(key: str, by: int = 1):
    sql = ("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
           "ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(settings.value AS INTEGER)+? AS TEXT), updated_at=excluded.updated_at")
    with db.conn() as c:
        c.execute(db._sql(sql), (key, str(by), datetime.utcnow().isoformat(sep=" ", timespec="seconds"), by))


def _get(key: str) -> int:
    r = db.get_setting(key)
    try:
        return int(r["value"]) if r and r["value"] is not None else 0
    except (TypeError, ValueError):
        return 0


def _is_bot() -> bool:
    try:
        ua = (st.context.headers.get("User-Agent") or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return any(w in ua for w in ("headless", "bot", "spider", "crawler", "monitor", "uptime"))


def count_visit():
    """Once per browser session; automated browsers (keep-alive pings, crawlers) are not counted."""
    if st.session_state.get("_visit_counted"):
        return
    st.session_state["_visit_counted"] = True
    if _is_bot():
        return
    try:
        _bump("stat:visits:total")
        _bump("stat:visits:" + datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    except Exception:  # noqa: BLE001 - a counter must never break a page
        pass


def count_download():
    try:
        _bump("stat:qr_downloads")
    except Exception:  # noqa: BLE001
        pass


@st.cache_data(ttl=60, show_spinner=False)
def snapshot() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    saved = db._one("SELECT COUNT(*) n FROM qrcodes")["n"]
    board = db._q("SELECT u.name, COUNT(q.id) n FROM qrcodes q JOIN users u ON u.id=q.user_id GROUP BY u.id, u.name ORDER BY n DESC, u.name LIMIT 5")
    return {"visits": _get("stat:visits:total"), "today": _get("stat:visits:" + today), "created": int(saved) + _get("stat:qr_downloads"),
            "board": [{"name": (b["name"] or "Creator").strip().split(" ")[0][:14], "n": int(b["n"])} for b in board]}
