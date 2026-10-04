import re

import bcrypt
import streamlit as st

from core import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    return None


def login(email, pw):
    u = db.get_user_by_email(email or "")
    if not u or not check_pw(pw or "", u["pw_hash"]):
        return "Incorrect email or password."
    st.session_state.uid = u["id"]
    return None


def logout():
    st.session_state.pop("uid", None)


def current_user():
    uid = st.session_state.get("uid")
    return db.get_user(uid) if uid else None
