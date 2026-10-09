"""Event booking data layer: events, bookings (one per attendee pass), organizers, and the gate scan log.
Works on both SQLite and Postgres through core.db (same SQL, `?` placeholders). All event times are Indian Standard Time (IST);
database timestamps stay UTC like the rest of the app."""
import json
import re
import secrets
from datetime import datetime as _datetime
from datetime import timedelta, timezone

from core import db
from core.plans import get_plan

IST = timezone(timedelta(hours=5, minutes=30))
REF_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"        # no 0/O/1/I/L: easy to read out at the gate
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BAD_PIN_LIMIT, BAD_PIN_WINDOW_MIN = 8, 10

# plan key -> (max events, max attendees per event). Edit here to change what each plan includes.
EVENT_LIMITS = {"free": (1, 50), "starter": (3, 300), "pro": (20, 2000), "business": (100, 20000)}


class BookingError(Exception):
    """A user-facing reason why a booking could not be made."""


# ----------------------------------------------------------------------------- time helpers
def now_ist() -> _datetime:
    return _datetime.now(IST).replace(tzinfo=None)


def utc_now_str() -> str:
    return _datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def utc_to_ist(utc_str: str | None) -> _datetime | None:
    if not utc_str:
        return None
    return _datetime.strptime(utc_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(IST).replace(tzinfo=None)


def fmt_utc(utc_str: str | None, fmt: str = "%d %b %Y, %I:%M %p") -> str:
    d = utc_to_ist(utc_str)
    return d.strftime(fmt) if d else ""


def ist_to_utc_str(d, t=None) -> str:
    """Date (+ optional time) entered in IST -> 'YYYY-MM-DD HH:MM:SS' UTC string for comparisons."""
    t = t or _datetime.min.time()
    dt = _datetime.combine(d, t).replace(tzinfo=IST).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def event_start(ev: dict) -> _datetime:
    return _datetime.strptime(f"{ev['event_date']} {ev['start_time'] or '00:00'}", "%Y-%m-%d %H:%M")


def event_end(ev: dict) -> _datetime:
    end = ev.get("end_time") or ev["start_time"] or "23:59"
    e = _datetime.strptime(f"{ev['event_date']} {end}", "%Y-%m-%d %H:%M")
    return e if e >= event_start(ev) else e + timedelta(days=1)


def deadline_dt(ev: dict) -> _datetime:
    return _datetime.strptime(ev["reg_deadline"], "%Y-%m-%d %H:%M") if ev.get("reg_deadline") else event_start(ev)


def _rand(alpha: str, n: int) -> str:
    return "".join(secrets.choice(alpha) for _ in range(n))


# ----------------------------------------------------------------------------- low-level
def _cur(c, sql, args=()):
    return c.execute(db._sql(sql), args)


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def _one(sql, args=()):
    return db._one(sql, args)


def _q(sql, args=()):
    return db._q(sql, args)


def _x(sql, args=()):
    return db._x(sql, args)


# ----------------------------------------------------------------------------- events
FIELDS = ("name", "description", "venue", "map_url", "event_date", "start_time", "end_time", "capacity", "reg_deadline", "max_tickets",
          "is_paid", "price", "upi_id", "upi_name", "pay_note", "collect_phone", "custom_label", "contact_info")


def validate_event(d: dict, plan_key: str, editing_id: int | None = None, owner_id: int | None = None) -> list[str]:
    """Returns a list of human-readable problems (empty = OK)."""
    errs = []
    if not (d.get("name") or "").strip():
        errs.append("Give the event a name.")
    if not (d.get("venue") or "").strip():
        errs.append("Add the venue (or 'Online').")
    try:
        start = _datetime.strptime(f"{d['event_date']} {d['start_time']}", "%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return errs + ["Pick a valid event date and start time."]
    if editing_id is None and start < now_ist():
        errs.append("The event start must be in the future.")
    if d.get("end_time"):
        try:
            _datetime.strptime(d["end_time"], "%H:%M")
        except Exception:  # noqa: BLE001
            errs.append("End time is not valid.")
    max_att = EVENT_LIMITS.get(plan_key, EVENT_LIMITS["free"])[1]
    cap = int(d.get("capacity") or 0)
    if cap < 1:
        errs.append("Capacity must be at least 1.")
    elif cap > max_att:
        errs.append(f"Your {get_plan(plan_key).name} plan allows up to {max_att:,} attendees per event. Upgrade for more.")
    if d.get("reg_deadline"):
        try:
            dl = _datetime.strptime(d["reg_deadline"], "%Y-%m-%d %H:%M")
            if dl > start:
                errs.append("The registration deadline must be before the event starts.")
        except Exception:  # noqa: BLE001
            errs.append("Registration deadline is not valid.")
    if not 1 <= int(d.get("max_tickets") or 1) <= 10:
        errs.append("Tickets per booking must be between 1 and 10.")
    if d.get("is_paid"):
        if int(d.get("price") or 0) < 1:
            errs.append("Enter a ticket price of at least 1 rupee, or switch to free registration.")
        upi = (d.get("upi_id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._\-]{2,}@[A-Za-z0-9]{2,}", upi):
            errs.append("Enter a valid UPI ID for payments (for example name@bank).")
    if d.get("map_url") and not str(d["map_url"]).lower().startswith(("http://", "https://")):
        errs.append("The map link must start with http:// or https://")
    if editing_id is None and owner_id is not None:
        max_events = EVENT_LIMITS.get(plan_key, EVENT_LIMITS["free"])[0]
        have = _one("SELECT COUNT(*) n FROM events WHERE owner_id=? AND status<>'cancelled'", (owner_id,))["n"]
        if have >= max_events:
            errs.append(f"Your {get_plan(plan_key).name} plan includes {max_events} active event(s). Cancel one or upgrade your plan.")
    return errs


def create_event(owner_id: int, d: dict) -> dict:
    code = _rand(CODE_ALPHABET, 8)
    while _one("SELECT 1 FROM events WHERE code=?", (code,)):
        code = _rand(CODE_ALPHABET, 8)
    vals = {k: d.get(k) for k in FIELDS}
    vals["name"] = vals["name"].strip()
    vals["reg_deadline"] = vals["reg_deadline"] or f"{d['event_date']} {d['start_time']}"
    for k in ("capacity", "max_tickets", "is_paid", "price", "collect_phone"):
        vals[k] = int(vals[k] or 0)
    cols = ["owner_id", "code", "staff_pin", *FIELDS]
    args = [owner_id, code, _rand("0123456789", 6), *[vals[k] for k in FIELDS]]
    eid = _x(f"INSERT INTO events({','.join(cols)}) VALUES({','.join('?' * len(cols))})", args)
    return get_event(eid)


def update_event(eid: int, d: dict):
    vals = {k: d.get(k) for k in FIELDS}
    for k in ("capacity", "max_tickets", "is_paid", "price", "collect_phone"):
        vals[k] = int(vals[k] or 0)
    vals["reg_deadline"] = vals["reg_deadline"] or f"{d['event_date']} {d['start_time']}"
    _x(f"UPDATE events SET {','.join(k + '=?' for k in FIELDS)} WHERE id=?", [*[vals[k] for k in FIELDS], eid])


def set_status(eid: int, status: str):
    _x("UPDATE events SET status=? WHERE id=?", (status, eid))


def new_pin(eid: int) -> str:
    pin = _rand("0123456789", 6)
    _x("UPDATE events SET staff_pin=? WHERE id=?", (pin, eid))
    return pin


def get_event(eid: int) -> dict | None:
    return _one("SELECT * FROM events WHERE id=?", (eid,))


def get_event_by_code(code: str) -> dict | None:
    return _one("SELECT * FROM events WHERE code=?", ((code or "").strip().lower(),))


def delete_event(eid: int) -> bool:
    if _one("SELECT 1 FROM bookings WHERE event_id=?", (eid,)):
        return False
    _x("DELETE FROM event_team WHERE event_id=?", (eid,))
    _x("DELETE FROM pass_scans WHERE event_id=?", (eid,))
    _x("DELETE FROM events WHERE id=?", (eid,))
    return True


_COUNTS = ("SELECT COUNT(*) FROM bookings b WHERE b.event_id=e.id AND b.status='{s}'")


def list_events(user_id: int, is_admin: bool = False) -> list[dict]:
    sql = ("SELECT e.*, u.email owner_email, u.name owner_name,"
           " (SELECT COUNT(*) FROM bookings b WHERE b.event_id=e.id AND b.status='confirmed') confirmed,"
           " (SELECT COUNT(*) FROM bookings b WHERE b.event_id=e.id AND b.status='pending_payment') pending,"
           " (SELECT COUNT(*) FROM bookings b WHERE b.event_id=e.id AND b.status='confirmed' AND b.checked_in_at IS NOT NULL) checked_in"
           " FROM events e JOIN users u ON u.id=e.owner_id ")
    if is_admin:
        return _q(sql + "ORDER BY e.event_date DESC, e.id DESC")
    return _q(sql + "WHERE e.owner_id=? OR e.id IN (SELECT event_id FROM event_team WHERE user_id=?) ORDER BY e.event_date DESC, e.id DESC", (user_id, user_id))


def can_manage(eid: int, user: dict) -> bool:
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    ev = get_event(eid)
    if ev and ev["owner_id"] == user["id"]:
        return True
    return bool(_one("SELECT 1 FROM event_team WHERE event_id=? AND user_id=?", (eid, user["id"])))


def team(eid: int) -> list[dict]:
    return _q("SELECT u.id, u.name, u.email, t.role FROM event_team t JOIN users u ON u.id=t.user_id WHERE t.event_id=? ORDER BY t.added_at", (eid,))


def add_team_member(eid: int, email: str) -> str | None:
    u = db.get_user_by_email(email or "")
    if not u:
        return "No QRForge account uses that email. Ask them to sign up first."
    ev = get_event(eid)
    if u["id"] == ev["owner_id"] or _one("SELECT 1 FROM event_team WHERE event_id=? AND user_id=?", (eid, u["id"])):
        return "That person already has access."
    with db.conn() as c:                      # event_team has a composite key and no id column, so no RETURNING id
        _cur(c, "INSERT INTO event_team(event_id,user_id) VALUES(?,?)", (eid, u["id"]))
    return None


def remove_team_member(eid: int, user_id: int):
    _x("DELETE FROM event_team WHERE event_id=? AND user_id=?", (eid, user_id))


def stats(eid: int) -> dict:
    r = _one("SELECT"
             " SUM(CASE WHEN status='confirmed' THEN 1 ELSE 0 END) confirmed,"
             " SUM(CASE WHEN status='pending_payment' THEN 1 ELSE 0 END) pending,"
             " SUM(CASE WHEN status IN ('cancelled','rejected') THEN 1 ELSE 0 END) cancelled,"
             " SUM(CASE WHEN status='confirmed' AND checked_in_at IS NOT NULL THEN 1 ELSE 0 END) checked_in,"
             " SUM(CASE WHEN status='confirmed' THEN amount ELSE 0 END) revenue"
             " FROM bookings WHERE event_id=?", (eid,))
    ev = get_event(eid)
    out = {k: int(r[k] or 0) for k in ("confirmed", "pending", "cancelled", "checked_in", "revenue")}
    out["capacity"] = ev["capacity"]
    out["remaining"] = max(0, ev["capacity"] - out["confirmed"] - out["pending"])
    out["rate"] = round(100 * out["checked_in"] / out["confirmed"]) if out["confirmed"] else 0
    return out


def registration_state(ev: dict) -> tuple[bool, str]:
    """Can people still book? -> (open, reason when closed)."""
    if ev["status"] == "cancelled":
        return False, "This event has been cancelled."
    if ev["status"] != "open":
        return False, "Registration for this event is closed."
    if now_ist() > event_end(ev):
        return False, "This event has ended."
    if now_ist() > deadline_dt(ev):
        return False, "The registration deadline has passed."
    if stats(ev["id"])["remaining"] <= 0:
        return False, "Sold out. All seats are taken."
    return True, ""


# ----------------------------------------------------------------------------- bookings
def create_bookings(ev: dict, names: list[str], email: str, phone: str = "", extra: str = "", pay_ref: str = "", pay_shot: str = "", pay_mime: str = "") -> list[dict]:
    """Atomically reserves seats (capacity-safe) and returns the created bookings. Free events are confirmed at once;
    paid events wait as 'pending_payment' until the organizer approves the payment."""
    email = (email or "").strip().lower()
    names = [n.strip() for n in names if n and n.strip()]
    if not names:
        raise BookingError("Enter the attendee name.")
    if not EMAIL_RE.match(email):
        raise BookingError("Enter a valid email address.")
    if len(names) > int(ev["max_tickets"]):
        raise BookingError(f"You can book up to {ev['max_tickets']} tickets at a time.")
    if any(len(n) > 80 for n in names) or len(email) > 120 or len(phone or "") > 20 or len(extra or "") > 200:
        raise BookingError("One of the fields is too long.")
    paid = bool(ev["is_paid"])
    if paid and not re.fullmatch(r"[A-Za-z0-9]{6,30}", (pay_ref or "").strip()):
        raise BookingError("Enter the UPI transaction ID (6 to 30 letters or digits) from your payment app.")
    group = _rand(REF_ALPHABET, 8)
    made = []
    with db.conn() as c:
        if db.USE_PG:
            _cur(c, "SELECT id FROM events WHERE id=? FOR UPDATE", (ev["id"],))
        else:
            c.execute("BEGIN IMMEDIATE")
        fresh = _rows(_cur(c, "SELECT * FROM events WHERE id=?", (ev["id"],)))[0]
        if fresh["status"] != "open":
            raise BookingError("Registration for this event is closed.")
        if now_ist() > deadline_dt(fresh):
            raise BookingError("The registration deadline has passed.")
        taken = _rows(_cur(c, "SELECT COUNT(*) n FROM bookings WHERE event_id=? AND status IN ('confirmed','pending_payment')", (ev["id"],)))[0]["n"]
        left = fresh["capacity"] - taken
        if left < len(names):
            raise BookingError("Sold out. All seats are taken." if left <= 0 else f"Only {left} seat(s) left. Reduce the number of tickets.")
        dup = _rows(_cur(c, "SELECT 1 x FROM bookings WHERE event_id=? AND LOWER(email)=? AND status IN ('confirmed','pending_payment')", (ev["id"], email)))
        if dup:
            raise BookingError("This email is already registered for this event. Use 'Find my pass' below to get your pass again.")
        if paid and _rows(_cur(c, "SELECT 1 x FROM bookings WHERE event_id=? AND LOWER(pay_ref)=?", (ev["id"], pay_ref.strip().lower()))):
            raise BookingError("That transaction ID has already been used for this event.")
        status = "pending_payment" if paid else "confirmed"
        for n in names:
            for _ in range(8):
                ref, token = "EVT-" + _rand(REF_ALPHABET, 6), secrets.token_urlsafe(12)
                if not _rows(_cur(c, "SELECT 1 x FROM bookings WHERE ref=? OR token=?", (ref, token))):
                    break
            args = (ev["id"], group, ref, token, n, email, (phone or "").strip(), (extra or "").strip(), status,
                    int(ev["price"] or 0) if paid else 0, (pay_ref or "").strip() or None, pay_shot or None, pay_mime or None)
            sql = ("INSERT INTO bookings(event_id,group_id,ref,token,name,email,phone,extra,status,amount,pay_ref,pay_shot,pay_mime)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
            _cur(c, sql, args)
            made.append({"ref": ref, "token": token, "name": n, "email": email, "status": status, "event_id": ev["id"], "group_id": group})
    return made


def get_booking(booking_id: int) -> dict | None:
    return _one("SELECT * FROM bookings WHERE id=?", (booking_id,))


def get_by_token(token: str) -> dict | None:
    return _one("SELECT * FROM bookings WHERE token=?", ((token or "").strip(),))


def get_by_ref(ref: str) -> dict | None:
    return _one("SELECT * FROM bookings WHERE ref=?", ((ref or "").strip().upper(),))


def group_bookings(group_id: str) -> list[dict]:
    return _q("SELECT * FROM bookings WHERE group_id=? ORDER BY id", (group_id,))


def bookings_for_email(ev_id: int, email: str) -> list[dict]:
    return _q("SELECT * FROM bookings WHERE event_id=? AND LOWER(email)=? AND status IN ('confirmed','pending_payment') ORDER BY id", (ev_id, (email or "").strip().lower()))


def search_bookings(event_ids: list[int], text: str = "", statuses: list[str] | None = None, checked: str = "all",
                    ci_from: str | None = None, ci_to: str | None = None, limit: int = 20000) -> list[dict]:
    """Attendee explorer: filter by event(s), free text (name/email/phone/booking ID), status, checked-in state and check-in time range
    (ci_from / ci_to are UTC 'YYYY-MM-DD HH:MM:SS' strings)."""
    if not event_ids:
        return []
    where, args = [f"b.event_id IN ({','.join('?' * len(event_ids))})"], list(event_ids)
    if text.strip():
        like = f"%{text.strip().lower()}%"
        where.append("(LOWER(b.name) LIKE ? OR LOWER(b.email) LIKE ? OR LOWER(b.ref) LIKE ? OR LOWER(COALESCE(b.phone,'')) LIKE ?)")
        args += [like] * 4
    if statuses:
        where.append(f"b.status IN ({','.join('?' * len(statuses))})")
        args += statuses
    if checked == "in":
        where.append("b.checked_in_at IS NOT NULL")
    elif checked == "not":
        where.append("b.checked_in_at IS NULL")
    if ci_from:
        where.append("b.checked_in_at >= ?")
        args.append(ci_from)
    if ci_to:
        where.append("b.checked_in_at <= ?")
        args.append(ci_to)
    sql = ("SELECT b.id, b.event_id, e.name event_name, e.event_date, b.ref, b.name, b.email, b.phone, b.extra, b.status, b.amount, b.pay_ref,"
           " b.token, b.checked_in_at, b.checked_in_by, b.created_at, b.cancelled_at, b.review_note, b.group_id,"
           " (CASE WHEN b.pay_shot IS NULL THEN 0 ELSE 1 END) has_shot"
           f" FROM bookings b JOIN events e ON e.id=b.event_id WHERE {' AND '.join(where)} ORDER BY b.id DESC LIMIT {int(limit)}")
    return _q(sql, args)


def payment_shot(booking_id: int) -> dict | None:
    return _one("SELECT pay_shot, pay_mime FROM bookings WHERE id=?", (booking_id,))


def approve(ids: list[int], by: str) -> list[dict]:
    done = []
    for i in ids:
        b = get_booking(i)
        if b and b["status"] == "pending_payment":
            _x("UPDATE bookings SET status='confirmed', review_note=? WHERE id=?", (f"approved by {by}", i))
            done.append(get_booking(i))
    return done


def reject(ids: list[int], by: str, reason: str = "") -> list[dict]:
    done = []
    for i in ids:
        b = get_booking(i)
        if b and b["status"] == "pending_payment":
            _x("UPDATE bookings SET status='rejected', cancelled_at=?, review_note=? WHERE id=?", (utc_now_str(), (reason or f"rejected by {by}")[:200], i))
            done.append(get_booking(i))
    return done


def cancel(ids: list[int], by: str, reason: str = "") -> list[dict]:
    done = []
    for i in ids:
        b = get_booking(i)
        if b and b["status"] in ("confirmed", "pending_payment"):
            _x("UPDATE bookings SET status='cancelled', cancelled_at=?, review_note=? WHERE id=?", (utc_now_str(), (reason or f"cancelled by {by}")[:200], i))
            done.append(get_booking(i))
    return done


# ----------------------------------------------------------------------------- gate scanning
def parse_pass_input(raw: str) -> tuple[str | None, str | None]:
    """Accepts the QR text (a pass link), a bare token, or a typed booking ID -> (token, ref)."""
    s = (raw or "").strip()
    if not s:
        return None, None
    m = re.search(r"[?&]pass=([A-Za-z0-9_\-]{8,40})", s)
    if m:
        return m.group(1), None
    if re.fullmatch(r"(?i)EVT-?[A-Z0-9]{6}", s):
        s = s.upper()
        return None, s if "-" in s else "EVT-" + s[3:]
    if re.fullmatch(r"[A-Za-z0-9_\-]{12,24}", s):
        return s, None
    return None, None


def _log_scan(event_id, booking_id, result, actor, detail=""):
    _x("INSERT INTO pass_scans(event_id,booking_id,ts,result,actor,detail) VALUES(?,?,?,?,?,?)", (event_id, booking_id, utc_now_str(), result, actor, (detail or "")[:200]))


def process_scan(ev: dict, raw: str, actor: str, mark: bool = True) -> dict:
    """Validates a scanned/typed pass for THIS event and (when mark=True) checks the attendee in.
    result in: valid | already_used | cancelled | unpaid | invalid | wrong_event | event_cancelled."""
    token, ref = parse_pass_input(raw)
    b = get_by_token(token) if token else (get_by_ref(ref) if ref else None)
    if ev["status"] == "cancelled":
        _log_scan(ev["id"], b["id"] if b else None, "event_cancelled", actor)
        return {"result": "event_cancelled", "booking": b, "message": "This event has been cancelled."}
    if not b:
        _log_scan(ev["id"], None, "invalid", actor, (raw or "")[:60])
        return {"result": "invalid", "booking": None, "message": "Not a valid pass for this system."}
    if b["event_id"] != ev["id"]:
        _log_scan(ev["id"], b["id"], "wrong_event", actor)
        return {"result": "wrong_event", "booking": None, "message": "This pass is for a different event."}
    if b["status"] in ("cancelled", "rejected"):
        _log_scan(ev["id"], b["id"], "cancelled", actor)
        return {"result": "cancelled", "booking": b, "message": "This booking was cancelled. Do not admit."}
    if b["status"] == "pending_payment":
        _log_scan(ev["id"], b["id"], "unpaid", actor)
        return {"result": "unpaid", "booking": b, "message": "Payment is not confirmed yet. Do not admit."}
    if b["checked_in_at"]:
        _log_scan(ev["id"], b["id"], "already_used", actor, b["checked_in_at"])
        return {"result": "already_used", "booking": b,
                "message": f"Already checked in at {fmt_utc(b['checked_in_at'], '%d %b, %I:%M %p')} by {b['checked_in_by'] or 'staff'}."}
    if not mark:
        return {"result": "valid", "booking": b, "message": "Valid pass (not yet checked in)."}
    ts = utc_now_str()
    with db.conn() as c:        # atomic: only one scan can win the check-in even if two phones scan at the same instant
        cur = _cur(c, "UPDATE bookings SET checked_in_at=?, checked_in_by=? WHERE id=? AND checked_in_at IS NULL AND status='confirmed'", (ts, actor[:60], b["id"]))
        won = cur.rowcount == 1
    if not won:
        b = get_booking(b["id"])
        _log_scan(ev["id"], b["id"], "already_used", actor, b["checked_in_at"] or "")
        return {"result": "already_used", "booking": b, "message": f"Already checked in at {fmt_utc(b['checked_in_at'], '%d %b, %I:%M %p')}."}
    _log_scan(ev["id"], b["id"], "valid", actor)
    return {"result": "valid", "booking": get_booking(b["id"]), "message": "Valid. Admit one."}


def undo_checkin(booking_id: int, actor: str):
    _x("UPDATE bookings SET checked_in_at=NULL, checked_in_by=NULL WHERE id=?", (booking_id,))
    b = get_booking(booking_id)
    _log_scan(b["event_id"], booking_id, "undo", actor)


def manual_checkin(booking_id: int, actor: str) -> dict:
    b = get_booking(booking_id)
    return process_scan(get_event(b["event_id"]), b["ref"], actor)


def pin_locked(eid: int) -> bool:
    since = (_datetime.now(timezone.utc) - timedelta(minutes=BAD_PIN_WINDOW_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    n = _one("SELECT COUNT(*) n FROM pass_scans WHERE event_id=? AND result='bad_pin' AND ts>=?", (eid, since))["n"]
    return n >= BAD_PIN_LIMIT


def verify_pin(ev: dict, pin: str) -> tuple[bool, str]:
    if pin_locked(ev["id"]):
        return False, f"Too many wrong PINs. Try again in {BAD_PIN_WINDOW_MIN} minutes."
    if secrets.compare_digest((pin or "").strip(), ev["staff_pin"] or "-"):
        return True, ""
    _log_scan(ev["id"], None, "bad_pin", "staff", "")
    return False, "Wrong PIN."


def recent_scans(eid: int, limit: int = 15) -> list[dict]:
    return _q("SELECT s.ts, s.result, s.actor, s.detail, b.ref, b.name FROM pass_scans s LEFT JOIN bookings b ON b.id=s.booking_id"
              " WHERE s.event_id=? AND s.result<>'bad_pin' ORDER BY s.id DESC LIMIT ?", (eid, limit))


def checkin_times(eid: int) -> list[str]:
    return [r["checked_in_at"] for r in _q("SELECT checked_in_at FROM bookings WHERE event_id=? AND status='confirmed' AND checked_in_at IS NOT NULL ORDER BY checked_in_at", (eid,))]


def booking_times(eid: int) -> list[str]:
    return [r["created_at"] for r in _q("SELECT created_at FROM bookings WHERE event_id=? AND status IN ('confirmed','pending_payment') ORDER BY created_at", (eid,))]


def organizer_contact(ev: dict) -> dict:
    return db.get_user(ev["owner_id"])
