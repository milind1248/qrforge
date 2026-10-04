"""Email notifications over SMTP (Gmail app password). Sent from a background thread so login never waits
on the mail server, and failures never block the user."""
import html
import logging
import smtplib
import threading
from email.message import EmailMessage

from core import db
from core.config import (APP_NAME, BASE_URL, NOTIFY_OWNER_LOGIN, NOTIFY_USER_LOGIN, OWNER_EMAIL, SMTP_HOST, SMTP_PASSWORD,
                         SMTP_PORT, SMTP_SENDER)

log = logging.getLogger("qrforge.notify")


def enabled() -> bool:
    return bool(SMTP_SENDER and SMTP_PASSWORD)


def _send(to: str, subject: str, text: str, body_html: str):
    msg = EmailMessage()
    msg["From"] = f"{APP_NAME} <{SMTP_SENDER}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(body_html, subtype="html")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(SMTP_SENDER, SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001
        log.warning("email to %s failed: %s", to, e)


def send_async(to: str, subject: str, text: str, body_html: str):
    if enabled() and to:
        threading.Thread(target=_send, args=(to, subject, text, body_html), daemon=True).start()


def _wrap(title: str, rows: list[tuple[str, str]], footer: str) -> str:
    trs = "".join(f"<tr><td style='padding:4px 14px 4px 0;color:#64748B'>{html.escape(k)}</td>"
                  f"<td style='padding:4px 0;font-weight:600'>{html.escape(v)}</td></tr>" for k, v in rows)
    return (f"<div style='font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:auto;color:#0F172A'>"
            f"<h2 style='color:#4F46E5;margin-bottom:4px'>{APP_NAME}</h2><h3 style='margin-top:0'>{html.escape(title)}</h3>"
            f"<table style='font-size:14px'>{trs}</table>"
            f"<p style='font-size:13px;color:#475569;margin-top:18px'>{footer}</p></div>")


def on_login(user: dict, when: str, device: str, os_: str, browser: str):
    """Login alert to the user, plus an admin copy to OWNER_EMAIL. Rate-limited to one per 10 min per user."""
    if not enabled() or not db.claim_login_alert(user["id"]):
        return
    rows = [("Account", user["email"]), ("Time (UTC)", when), ("Device", f"{device} · {os_} · {browser}"),
            ("Plan", user["plan"].title())]
    if NOTIFY_USER_LOGIN:
        text = (f"New login to your {APP_NAME} account {user['email']} at {when} UTC from {device} ({os_}, {browser}).\n"
                f"If this was not you, change your password at {BASE_URL} (My account > Account).")
        send_async(user["email"], f"New login to your {APP_NAME} account", text,
                   _wrap("New login detected", rows,
                         f"If this was not you, <a href='{BASE_URL}'>sign in</a> and change your password "
                         "from My account → Account."))
    if NOTIFY_OWNER_LOGIN and OWNER_EMAIL and OWNER_EMAIL.lower() != user["email"].lower():
        send_async(OWNER_EMAIL, f"[{APP_NAME}] {user['name']} just logged in",
                   "Login: " + "; ".join(f"{k}: {v}" for k, v in rows), _wrap("User login", rows, "Admin notification."))


def on_signup(user: dict, when: str):
    rows = [("Name", user["name"]), ("Email", user["email"]), ("Time (UTC)", when)]
    send_async(user["email"], f"Welcome to {APP_NAME}",
               f"Hi {user['name']}, your {APP_NAME} account is ready. Start creating QR codes at {BASE_URL}",
               _wrap(f"Welcome, {user['name']}!", [("Account", user["email"]), ("Plan", "Free")],
                     f"Your account is ready. <a href='{BASE_URL}'>Create your first QR code</a>."))
    if OWNER_EMAIL and OWNER_EMAIL.lower() != user["email"].lower():
        send_async(OWNER_EMAIL, f"[{APP_NAME}] New signup: {user['email']}",
                   "New signup: " + "; ".join(f"{k}: {v}" for k, v in rows), _wrap("New signup", rows, "Admin notification."))
