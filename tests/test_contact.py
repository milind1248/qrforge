from email import message_from_string

from core import contact, notify


def test_contact_message_goes_to_owner_with_reply_to(monkeypatch):
    sent = {}

    def fake_send(to, subject, text, body_html, attachments=(), reply_to="", raise_errors=False):
        sent.update(to=to, subject=subject, text=text, html=body_html, reply_to=reply_to, raise_errors=raise_errors)

    monkeypatch.setattr(notify, "enabled", lambda: True)
    monkeypatch.setattr(notify, "OWNER_EMAIL", "owner@test.local")
    monkeypatch.setattr(notify, "_send", fake_send)
    assert notify.send_contact_message("Asha", "asha@x.com", "Help <b>please</b>", "Line one\n<script>alert(1)</script>") is True
    assert sent["to"] == "owner@test.local" and sent["reply_to"] == "asha@x.com" and sent["raise_errors"] is True
    assert "Help" in sent["subject"] and "<script>" not in sent["html"]          # visitor text is HTML-escaped in the email


def test_contact_failure_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(notify, "enabled", lambda: True)
    monkeypatch.setattr(notify, "OWNER_EMAIL", "owner@test.local")
    monkeypatch.setattr(notify, "_send", boom)
    assert notify.send_contact_message("A", "a@x.com", "S", "message body here") is False
    monkeypatch.setattr(notify, "enabled", lambda: False)                          # email switched off -> False, nothing sent
    assert notify.send_contact_message("A", "a@x.com", "S", "message body here") is False


def test_headers_cannot_be_injected_and_reply_to_is_set(monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): captured["raw"] = msg.as_string()

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(notify, "SMTP_SENDER", "sender@test.local")
    monkeypatch.setattr(notify, "SMTP_PASSWORD", "x")
    notify._send("owner@test.local", "Subject", "text", "<p>html</p>", reply_to="asha@x.com", raise_errors=True)
    m = message_from_string(captured["raw"])
    assert m["Reply-To"] == "asha@x.com" and m["To"] == "owner@test.local"
    assert contact._clean_line("Hi\r\nBcc: evil@x.com", 100) == "Hi Bcc: evil@x.com"   # newlines in a typed subject never reach a header
