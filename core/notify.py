"""Email notifications over SMTP (Gmail app password). Sent from a background thread so login never waits
on the mail server, and failures never block the user."""
import html
import logging
import smtplib
import threading
from datetime import datetime
from email.message import EmailMessage

from core import db
from core.config import (NO_EMAIL, APP_NAME, BASE_URL, NOTIFY_OWNER_LOGIN, NOTIFY_USER_LOGIN, OWNER_EMAIL, SMTP_HOST, SMTP_PASSWORD,
                         SMTP_PORT, SMTP_SENDER)

log = logging.getLogger("qrforge.notify")


def enabled() -> bool:
    return bool(SMTP_SENDER and SMTP_PASSWORD) and not NO_EMAIL


def _send(to: str, subject: str, text: str, body_html: str, attachments=(), reply_to: str = "", raise_errors: bool = False):
    msg = EmailMessage()
    msg["From"] = f"{APP_NAME} <{SMTP_SENDER}>"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    msg.add_alternative(body_html, subtype="html")
    for name, data, mime in attachments:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(SMTP_SENDER, SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001
        log.warning("email to %s failed: %s", to, e)
        if raise_errors:
            raise


def send_contact_message(name: str, email: str, subject: str, message: str) -> bool:
    """Contact-form message to the site owner (Reply-To = the visitor). Sent synchronously so the form can say whether it worked."""
    if not enabled() or not OWNER_EMAIL:
        return False
    rows = [("From", f"{name or '-'} <{email}>"), ("Query", subject), ("Time (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M"))]
    body = _wrap("New contact message", rows, "<br>".join(html.escape(message).splitlines()) + "<br><br>Reply to this email to answer the sender.")
    text = "\n".join(f"{k}: {v}" for k, v in rows) + "\n\n" + message
    try:
        _send(OWNER_EMAIL, f"[{APP_NAME}] Contact: {subject[:80]}", text, body, reply_to=email, raise_errors=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def send_async(to: str, subject: str, text: str, body_html: str, attachments=()):
    if enabled() and to:
        threading.Thread(target=_send, args=(to, subject, text, body_html, attachments), daemon=True).start()


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


def on_claim_submitted(user: dict, plan: str, period: str, paid: int, expected: int, ref: str, pay_date: str,
                       notes: str, shot: bytes, shot_mime: str):
    rows = [("User", f"{user['name']} <{user['email']}>"), ("Plan", f"{plan.title()} ({period})"),
            ("Amount paid", f"Rs {paid:,}"), ("Expected", f"Rs {expected:,}" + ("" if paid == expected else "  (MISMATCH)")),
            ("Payment date", pay_date), ("UPI reference", ref or "-"), ("Notes", notes or "-")]
    if OWNER_EMAIL:
        send_async(OWNER_EMAIL, f"[{APP_NAME}] Payment claim: {user['email']} - {plan.title()} Rs {paid:,}",
                   "Payment claim to review\n" + "\n".join(f"{k}: {v}" for k, v in rows),
                   _wrap("Payment claim to review", rows, f"Review it under Admin → Payment claims at {BASE_URL}. Screenshot attached."),
                   attachments=[("payment-screenshot.jpg", shot, shot_mime)])
    send_async(user["email"], f"We received your {APP_NAME} payment claim",
               f"Hi {user['name']}, we received your payment claim for the {plan.title()} plan (Rs {paid:,}). "
               "We will verify it and activate your plan shortly, usually within a day.",
               _wrap("Payment claim received", [("Plan", f"{plan.title()} ({period})"), ("Amount", f"Rs {paid:,}"),
                                                ("Status", "Under review")],
                     "We will verify your payment and activate your plan, usually within a day. You will get another email once it is approved."))


def on_claim_decision(user_row: dict, plan: str, period: str, approved: bool, reason: str = ""):
    """user_row needs email + name."""
    if approved:
        send_async(user_row["email"], f"Your {APP_NAME} {plan.title()} plan is active",
                   f"Hi {user_row['name']}, your payment is verified and the {plan.title()} plan ({period}) is now active. {BASE_URL}",
                   _wrap("Your plan is active", [("Plan", f"{plan.title()} ({period})"), ("Status", "Active")],
                         f"Thank you! <a href='{BASE_URL}'>Open QR Sugi</a> to use your new features."))
    else:
        send_async(user_row["email"], f"Your {APP_NAME} payment claim could not be verified",
                   f"Hi {user_row['name']}, we could not verify your payment claim for the {plan.title()} plan. {reason}",
                   _wrap("Payment claim not approved", [("Plan", f"{plan.title()} ({period})"), ("Reason", reason or "Not specified")],
                         "If you believe this is a mistake, submit a new claim with a clear screenshot of the successful payment, or reply to this email."))
