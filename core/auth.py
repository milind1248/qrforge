import re

import bcrypt
import streamlit as st

from datetime import datetime, timezone

from core import db, notify, ui

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def signup(email, name, pw):
    if not EMAIL_RE.match(email or ""):
        return "Please enter a valid email address."
    if len(pw or "") < 8:
        return "Password must be at least 8 characters."
    if not (name or "").strip():
        return "Please enter your name."
    if db.get_user_by_email(email):
        return "An account with this email already exists."
    st.session_state.uid = db.create_user(email, name, hash_pw(pw))
    try:
        user = db.get_user(st.session_state.uid)
        db.claim_login_alert(user["id"])  # signup counts as the first login; skip a duplicate login alert
        notify.on_signup(user, _now())
    except Exception:  # noqa: BLE001  never let email problems break signup
        pass
    return None


def login(email, pw):
    u = db.get_user_by_email(email or "")
    if not u or not check_pw(pw or "", u["pw_hash"]):
        return "Incorrect email or password."
    st.session_state.uid = u["id"]
    try:
        try:
            ua = st.context.headers.get("User-Agent", "")
        except Exception:  # noqa: BLE001
            ua = ""
        device, os_, browser = ui.parse_ua(ua)
        notify.on_login(u, _now(), device, os_, browser)
    except Exception:  # noqa: BLE001  never let email problems break login
        pass
    return None


def logout():
    st.session_state.pop("uid", None)


def current_user():
    uid = st.session_state.get("uid")
    return db.get_user(uid) if uid else None
