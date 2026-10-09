import threading
from datetime import timedelta

import pytest

from core import auth, event_db as E


def _future(days=7, hh="18:00"):
    return (E.now_ist() + timedelta(days=days)).strftime("%Y-%m-%d"), hh


def _event_data(**kw):
    d, t = _future()
    base = dict(name="Diwali Meetup", description="Fun", venue="Pune Hall", map_url="", event_date=d, start_time=t, end_time="21:00", capacity=3,
                reg_deadline="", max_tickets=3, is_paid=0, price=0, upi_id="", upi_name="", pay_note="", collect_phone=1, custom_label="", contact_info="")
    base.update(kw)
    return base


@pytest.fixture()
def org(fresh_db):
    uid = fresh_db.create_user("org@test.local", "Organizer", auth.hash_pw("x" * 10))
    fresh_db.set_plan(uid, "pro", "yearly")
    return fresh_db.get_user(uid)


def test_validation_rules(org):
    assert E.validate_event(_event_data(), "pro", owner_id=org["id"]) == []
    bad = E.validate_event(_event_data(name="", capacity=0, is_paid=1, price=0, upi_id="nope"), "pro", owner_id=org["id"])
    assert any("name" in e for e in bad) and any("Capacity" in e for e in bad) and any("price" in e for e in bad) and any("UPI" in e for e in bad)
    past = _event_data(event_date="2020-01-01")
    assert any("future" in e for e in E.validate_event(past, "pro", owner_id=org["id"]))
    assert any("plan allows" in e for e in E.validate_event(_event_data(capacity=51), "free", owner_id=org["id"]))
    late = _event_data(reg_deadline=f"{_future(30)[0]} 10:00")
    assert any("deadline" in e for e in E.validate_event(late, "pro", owner_id=org["id"]))


def test_plan_limits_number_of_events(org, fresh_db):
    fresh_db.set_plan(org["id"], "free")
    E.create_event(org["id"], _event_data())
    errs = E.validate_event(_event_data(name="Two"), "free", owner_id=org["id"])
    assert any("active event" in e for e in errs)


def test_free_booking_flow_and_capacity(org):
    ev = E.create_event(org["id"], _event_data())
    assert len(ev["code"]) == 8 and len(ev["staff_pin"]) == 6
    made = E.create_bookings(ev, ["Asha", "Ben"], "asha@x.com", "99999")
    assert [m["status"] for m in made] == ["confirmed", "confirmed"] and made[0]["ref"].startswith("EVT-") and len(made[0]["token"]) >= 12
    assert E.stats(ev["id"])["remaining"] == 1
    with pytest.raises(E.BookingError, match="already registered"):
        E.create_bookings(ev, ["Asha"], "ASHA@x.com")
    with pytest.raises(E.BookingError, match="Only 1 seat"):
        E.create_bookings(ev, ["C", "D"], "c@x.com")
    E.create_bookings(ev, ["Cy"], "c@x.com")
    with pytest.raises(E.BookingError, match="Sold out"):
        E.create_bookings(ev, ["Di"], "d@x.com")
    assert E.registration_state(E.get_event(ev["id"]))[0] is False


def test_capacity_is_race_safe(org):
    ev = E.create_event(org["id"], _event_data(capacity=5, max_tickets=1))
    results = []

    def book(i):
        try:
            E.create_bookings(ev, [f"P{i}"], f"p{i}@x.com")
            results.append("ok")
        except E.BookingError:
            results.append("full")
    ts = [threading.Thread(target=book, args=(i,)) for i in range(15)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count("ok") == 5 and E.stats(ev["id"])["confirmed"] == 5


def test_deadline_and_status_close_registration(org):
    soon = (E.now_ist() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
    ev = E.create_event(org["id"], _event_data(reg_deadline=soon))
    ok, why = E.registration_state(E.get_event(ev["id"]))
    assert not ok and "deadline" in why
    with pytest.raises(E.BookingError, match="deadline"):
        E.create_bookings(ev, ["A"], "a@x.com")
    ev2 = E.create_event(org["id"], _event_data(name="Second"))
    E.set_status(ev2["id"], "closed")
    with pytest.raises(E.BookingError, match="closed"):
        E.create_bookings(E.get_event(ev2["id"]), ["A"], "a@x.com")


def test_paid_flow_payment_review(org):
    ev = E.create_event(org["id"], _event_data(is_paid=1, price=499, upi_id="shop@upi", upi_name="Shop"))
    with pytest.raises(E.BookingError, match="transaction ID"):
        E.create_bookings(ev, ["A"], "a@x.com", pay_ref="")
    made = E.create_bookings(ev, ["A"], "a@x.com", pay_ref="UTR123456789")
    assert made[0]["status"] == "pending_payment"
    with pytest.raises(E.BookingError, match="already been used"):
        E.create_bookings(ev, ["B"], "b@x.com", pay_ref="utr123456789")
    st = E.stats(ev["id"])
    assert st["pending"] == 1 and st["confirmed"] == 0 and st["remaining"] == 2          # pending payments hold a seat
    b = E.get_by_ref(made[0]["ref"])
    assert E.process_scan(ev, b["token"], "gate")["result"] == "unpaid"
    assert len(E.approve([b["id"]], "org")) == 1 and E.get_booking(b["id"])["status"] == "confirmed"
    assert E.stats(ev["id"])["revenue"] == 499
    made2 = E.create_bookings(ev, ["C"], "c@x.com", pay_ref="UTR999888777")
    E.reject([E.get_by_ref(made2[0]["ref"])["id"]], "org", "no money received")
    assert E.stats(ev["id"])["remaining"] == 2                                           # rejected frees the seat


def test_scan_results(org):
    ev = E.create_event(org["id"], _event_data())
    other = E.create_event(org["id"], _event_data(name="Other"))
    a, b_ = E.create_bookings(ev, ["Asha", "Ben"], "a@x.com")
    oth = E.create_bookings(other, ["Zed"], "z@x.com")[0]
    link = f"https://app.example/?pass={a['token']}"
    r1 = E.process_scan(ev, link, "gate1")
    assert r1["result"] == "valid" and r1["booking"]["checked_in_by"] == "gate1"
    r2 = E.process_scan(ev, a["token"], "gate2")
    assert r2["result"] == "already_used" and "gate1" in r2["message"]
    assert E.process_scan(ev, b_["ref"].lower(), "gate")["result"] == "valid"            # typed booking ID, any case
    assert E.process_scan(ev, "EVT-ZZZZZZ", "gate")["result"] == "invalid"
    assert E.process_scan(ev, "garbage", "gate")["result"] == "invalid"
    assert E.process_scan(ev, oth["token"], "gate")["result"] == "wrong_event"
    E.cancel([E.get_by_ref(b_["ref"])["id"]], "org")
    assert E.process_scan(ev, b_["token"], "gate")["result"] == "cancelled"
    E.set_status(ev["id"], "cancelled")
    assert E.process_scan(E.get_event(ev["id"]), a["token"], "gate")["result"] == "event_cancelled"
    log = E.recent_scans(ev["id"], 50)
    assert {x["result"] for x in log} >= {"valid", "already_used", "invalid", "wrong_event", "cancelled"}


def test_double_scan_race_only_one_wins(org):
    ev = E.create_event(org["id"], _event_data())
    a = E.create_bookings(ev, ["Asha"], "a@x.com")[0]
    out = []
    ts = [threading.Thread(target=lambda: out.append(E.process_scan(ev, a["token"], "g")["result"])) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out.count("valid") == 1 and out.count("already_used") == 7


def test_undo_and_pin_throttle(org):
    ev = E.create_event(org["id"], _event_data())
    a = E.create_bookings(ev, ["Asha"], "a@x.com")[0]
    E.process_scan(ev, a["token"], "g")
    bid = E.get_by_ref(a["ref"])["id"]
    E.undo_checkin(bid, "org")
    assert E.get_booking(bid)["checked_in_at"] is None
    assert E.verify_pin(ev, ev["staff_pin"]) == (True, "")
    for _ in range(E.BAD_PIN_LIMIT):
        assert E.verify_pin(ev, "000000")[0] is False
    ok, msg = E.verify_pin(ev, ev["staff_pin"])
    assert ok is False and "Too many" in msg


def test_search_filters_and_team(org, fresh_db):
    ev = E.create_event(org["id"], _event_data(capacity=10))
    ev2 = E.create_event(org["id"], _event_data(name="Second", capacity=10))
    ba = E.create_bookings(ev, ["Asha Rao", "Ben Cole"], "asha@x.com", "98200")
    E.create_bookings(ev2, ["Zed"], "zed@x.com")
    E.process_scan(ev, ba[0]["token"], "gate")
    ids = [ev["id"], ev2["id"]]
    assert len(E.search_bookings(ids)) == 3
    assert [r["name"] for r in E.search_bookings(ids, text="rao")] == ["Asha Rao"]
    assert len(E.search_bookings(ids, text="ASHA@X")) == 2
    assert len(E.search_bookings(ids, text=ba[1]["ref"].lower())) == 1
    assert len(E.search_bookings(ids, checked="in")) == 1 and len(E.search_bookings(ids, checked="not")) == 2
    today = E.now_ist().date()
    assert len(E.search_bookings(ids, ci_from=E.ist_to_utc_str(today), ci_to=E.ist_to_utc_str(today + timedelta(days=1)))) == 1
    assert E.search_bookings(ids, ci_from=E.ist_to_utc_str(today + timedelta(days=1))) == []
    assert len(E.search_bookings([ev2["id"]])) == 1
    other = fresh_db.create_user("co@test.local", "Co", auth.hash_pw("x" * 10))
    assert E.can_manage(ev["id"], fresh_db.get_user(other)) is False
    assert E.add_team_member(ev["id"], "co@test.local") is None and E.can_manage(ev["id"], fresh_db.get_user(other)) is True
    assert E.add_team_member(ev["id"], "nobody@test.local") is not None
    assert len(E.list_events(other)) == 1 and len(E.list_events(org["id"])) == 2
    assert E.delete_event(ev["id"]) is False and E.delete_event(E.create_event(org["id"], _event_data(name="Empty"))["id"]) is True
