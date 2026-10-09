from datetime import timedelta

import pytest

from core import auth, event_db as E, event_mail, event_pass as P, notify


def _data(**kw):
    d = (E.now_ist() + timedelta(days=5)).strftime("%Y-%m-%d")
    base = dict(name="Expo", description="", venue="Hall", map_url="", event_date=d, start_time="10:00", end_time="12:00", capacity=3, reg_deadline="",
                max_tickets=2, is_paid=0, price=0, upi_id="", upi_name="", pay_note="", collect_phone=1, custom_label="", contact_info="help@expo.test")
    base.update(kw)
    return base


@pytest.fixture()
def org(fresh_db):
    uid = fresh_db.create_user("boss@test.local", "Boss", auth.hash_pw("x" * 10))
    return fresh_db.get_user(uid)


def test_email_has_qr_pass_event_link_organizer_and_cancel_link(org, monkeypatch):
    ev = E.create_event(org["id"], _data())
    b = E.get_by_token(E.create_bookings(ev, ["Asha"], "a@x.com")[0]["token"])
    sent = []
    monkeypatch.setattr(notify, "enabled", lambda: True)
    monkeypatch.setattr(notify, "send_async", lambda to, subj, text, html, attachments=(): sent.append((to, subj, text, html, attachments)))
    event_mail.send_passes(ev, [b])
    to, subj, text, html, atts = sent[0]
    assert to == "a@x.com" and b["ref"] in subj
    for needle in (P.cancel_url(b["token"]), P.event_url(ev["code"]), P.pass_url(b["token"]), "boss@test.local", "help@expo.test"):
        assert needle in text and needle in html.replace("&amp;", "&") or needle in text
    assert P.cancel_url(b["token"]) in html and P.event_url(ev["code"]) in html and "boss@test.local" in html
    assert any(a[0].endswith(".pdf") for a in atts)                     # the QR pass is attached


def test_attendee_cancel_rules_and_report(org):
    ev = E.create_event(org["id"], _data(is_paid=1, price=100, upi_id="x@bank", upi_name="X"))
    made = E.create_bookings(ev, ["Pay"], "p@x.com", pay_ref="ABC123XYZ9")
    b = E.get_by_token(made[0]["token"])
    assert E.attendee_can_cancel(ev, b)[0]
    E.cancel([b["id"]], "attendee", "cancelled by attendee")
    b = E.get_booking(b["id"])
    assert b["status"] == "cancelled" and b["cancelled_at"] and b["review_note"] == "cancelled by attendee"
    ok, why = E.attendee_can_cancel(ev, b)
    assert not ok and "already cancelled" in why
    row = E.search_bookings([ev["id"]])[0]                               # organizer report shows it, with who cancelled
    assert row["status"] == "cancelled" and row["review_note"] == "cancelled by attendee"
    assert E.stats(ev["id"])["cancelled"] == 1 and E.stats(ev["id"])["remaining"] == 3


def test_cannot_cancel_after_checkin_or_when_ended(org):
    ev = E.create_event(org["id"], _data())
    b = E.get_by_token(E.create_bookings(ev, ["Z"], "z@x.com")[0]["token"])
    E.process_scan(ev, b["ref"], "gate")
    ok, why = E.attendee_can_cancel(ev, E.get_booking(b["id"]))
    assert not ok and "checked in" in why
    past = dict(ev, event_date="2020-01-01", start_time="10:00", end_time="11:00")
    assert not E.attendee_can_cancel(past, b | {"checked_in_at": None})[0]


def test_organizer_adds_registrations(org):
    ev = E.create_event(org["id"], _data(is_paid=1, price=250, upi_id="x@bank", upi_name="X"))
    a = E.create_bookings(ev, ["Walk In"], "w@x.com", by="Boss")[0]
    assert a["status"] == "confirmed"                                    # no payment proof needed for organizer adds
    b = E.create_bookings(ev, ["Vip"], "w@x.com", by="Boss", amount=0)[0]   # same email allowed, complimentary
    rows = {r["name"]: r for r in E.search_bookings([ev["id"]])}
    assert rows["Walk In"]["amount"] == 250 and rows["Vip"]["amount"] == 0 and rows["Vip"]["review_note"] == "added by Boss"
    assert E.stats(ev["id"])["revenue"] == 250
    E.set_status(ev["id"], "closed")                                     # organizer can still add after registration closes
    E.create_bookings(ev, ["Late"], "l@x.com", by="Boss")
    with pytest.raises(E.BookingError):                                  # ... but never beyond capacity
        E.create_bookings(ev, ["Over"], "o@x.com", by="Boss")
    with pytest.raises(E.BookingError):                                  # and public booking stays closed
        E.create_bookings(ev, ["Pub"], "pub@x.com", pay_ref="ZZZ123456")
    E.set_status(ev["id"], "cancelled")
    with pytest.raises(E.BookingError):
        E.create_bookings(ev, ["X"], "x@x.com", by="Boss")
