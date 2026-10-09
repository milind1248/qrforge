"""Site counters for the sidebar: visits, QR codes created, and the creators leaderboard. Counters live in the existing `settings` table."""
from datetime import datetime, timedelta, timezone

import streamlit as st

from core import db


IST = timezone(timedelta(hours=5, minutes=30))


def _today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


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
        _bump("stat:visits:" + _today())
    except Exception:  # noqa: BLE001 - a counter must never break a page
        pass


def count_download():
    try:
        _bump("stat:qr_downloads")
        _bump("stat:qr_downloads:" + _today())
    except Exception:  # noqa: BLE001
        pass


@st.cache_data(ttl=60, show_spinner=False)
def snapshot(days: int = 7) -> dict:
    """Totals plus QR codes created per day (saved codes + downloads) for the last `days` days, IST."""
    today = datetime.now(IST).date()
    series = [(today - timedelta(days=i)) for i in range(days - 1, -1, -1)]
    per = {d.strftime("%Y-%m-%d"): 0 for d in series}
    since = (datetime.now(timezone.utc) - timedelta(days=days + 1)).strftime("%Y-%m-%d %H:%M:%S")
    for r in db._q("SELECT created_at FROM qrcodes WHERE created_at >= ?", (since,)):
        try:
            t = datetime.fromisoformat(str(r["created_at"])).replace(tzinfo=timezone.utc).astimezone(IST).strftime("%Y-%m-%d")
        except ValueError:
            continue
        if t in per:
            per[t] += 1
    for k in per:
        per[k] += _get("stat:qr_downloads:" + k)
    saved = db._one("SELECT COUNT(*) n FROM qrcodes")["n"]
    return {"visits": _get("stat:visits:total"), "today": _get("stat:visits:" + _today()), "created": int(saved) + _get("stat:qr_downloads"),
            "days": [{"date": d, "wd": d.weekday(), "label": d.strftime("%d"), "n": per[d.strftime("%Y-%m-%d")]} for d in series]}
