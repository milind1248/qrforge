"""Local SQLite data layer. Every function here maps 1:1 to a Supabase/Postgres call later,
so swapping the backend only means rewriting this module."""
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone


class _DT(datetime):
    @classmethod
    def utcnow(cls):  # naive UTC, without the deprecated datetime.utcnow()
        return datetime.now(timezone.utc).replace(tzinfo=None)


datetime = _DT  # noqa: A001

from core import license as _license
from core.config import DATABASE_URL, DB_PATH

USE_PG = bool(DATABASE_URL)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, name TEXT,
  pw_hash TEXT NOT NULL, role TEXT DEFAULT 'user', plan TEXT DEFAULT 'free',
  period TEXT, plan_expires TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS qrcodes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT, qr_type TEXT,
  content TEXT, is_dynamic INTEGER DEFAULT 0, short_code TEXT UNIQUE, dest TEXT,
  style TEXT, active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  rules TEXT, campaign TEXT, trust_preview INTEGER DEFAULT 0, health TEXT, health_at TEXT);
CREATE TABLE IF NOT EXISTS scans(
  id INTEGER PRIMARY KEY AUTOINCREMENT, qr_id INTEGER NOT NULL, ts TEXT DEFAULT CURRENT_TIMESTAMP,
  device TEXT, os TEXT, browser TEXT, lang TEXT, visitor TEXT, outcome TEXT, variant TEXT);
CREATE INDEX IF NOT EXISTS ix_scans_qr ON scans(qr_id, ts);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan TEXT, period TEXT,
  amount INTEGER, coupon TEXT, provider TEXT, status TEXT, txn_ref TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT, mime TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, qr_id INTEGER NOT NULL, reason TEXT, note TEXT,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL, code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL, description TEXT, venue TEXT, map_url TEXT,
  event_date TEXT, start_time TEXT, end_time TEXT,
  capacity INTEGER DEFAULT 100, reg_deadline TEXT, max_tickets INTEGER DEFAULT 5,
  is_paid INTEGER DEFAULT 0, price INTEGER DEFAULT 0, upi_id TEXT, upi_name TEXT, pay_note TEXT,
  collect_phone INTEGER DEFAULT 1, custom_label TEXT, contact_info TEXT,
  staff_pin TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS event_team(
  event_id INTEGER NOT NULL, user_id INTEGER NOT NULL, role TEXT DEFAULT 'organizer',
  added_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(event_id, user_id));
CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, group_id TEXT,
  ref TEXT UNIQUE NOT NULL, token TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT, extra TEXT, status TEXT DEFAULT 'confirmed',
  amount INTEGER DEFAULT 0, pay_ref TEXT, pay_shot TEXT, pay_mime TEXT, review_note TEXT,
  checked_in_at TEXT, checked_in_by TEXT, cancelled_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_bookings_event ON bookings(event_id, status);
CREATE INDEX IF NOT EXISTS ix_bookings_email ON bookings(event_id, email);
CREATE TABLE IF NOT EXISTS pass_scans(
  id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, booking_id INTEGER,
  ts TEXT DEFAULT CURRENT_TIMESTAMP, result TEXT, actor TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS ix_pass_scans_event ON pass_scans(event_id, ts);
"""

MIGRATIONS = {  # table -> {column: type}; keeps older local databases working
    "qrcodes": {"rules": "TEXT", "campaign": "TEXT", "trust_preview": "INTEGER DEFAULT 0",
                "health": "TEXT", "health_at": "TEXT"},
    "users": {"last_alert": "TEXT"},
    "payments": {"screenshot": "TEXT", "screenshot_mime": "TEXT", "pay_date": "TEXT", "notes": "TEXT",
                 "reviewed_by": "TEXT", "reviewed_at": "TEXT"},
    "scans": {"lang": "TEXT", "visitor": "TEXT", "outcome": "TEXT", "variant": "TEXT"},
}


PG_SCHEMA = "qrforge"
PG_TS = "to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')"


def _pg_schema() -> str:
    """Same tables as SCHEMA, in Postgres dialect. Timestamps stay TEXT so the app code is backend-neutral."""
    t = (SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
         .replace("DEFAULT CURRENT_TIMESTAMP", f"DEFAULT ({PG_TS})"))
    tables = ["users", "qrcodes", "scans", "payments", "reports", "settings", "events", "event_team", "bookings", "pass_scans"]
    rls = "".join(f"ALTER TABLE {n} ENABLE ROW LEVEL SECURITY;" for n in tables)  # block the public anon API
    return t + rls


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        def configure(c):  # isolate QRForge in its own schema: never touches other apps' tables in `public`
            c.execute(f"SET search_path TO {PG_SCHEMA}")
            c.commit()

        _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=4, open=True, configure=configure,
                               kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": False})
    return _pool


@contextmanager
def conn():
    if not _license.is_valid():
        raise RuntimeError("License key missing or invalid")
    if USE_PG:
        with _get_pool().connection() as c:
            yield c
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


_PG_TABLES = {"users", "qrcodes", "scans", "payments", "reports", "settings", "events", "event_team", "bookings", "pass_scans"}


def _pg_ready(c) -> bool:
    """Read-only check (takes no table locks): are all tables and migrated columns already present?"""
    rows = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=%s",
                     (PG_SCHEMA,)).fetchall()
    have = {(r["table_name"], r["column_name"]) for r in rows}
    if not _PG_TABLES <= {t for t, _ in have}:
        return False
    return all((t, col) in have for t, cols in MIGRATIONS.items() for col in cols)


def init_db():
    if USE_PG:
        with conn() as c:
            if _pg_ready(c):          # normal case: nothing to do, no DDL, no locks, no deadlocks
                return
            c.execute("SELECT pg_advisory_xact_lock(727274)")   # one process at a time may run DDL
            if _pg_ready(c):          # someone else finished while we waited
                return
            c.execute(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}")
            for stmt in [x for x in _pg_schema().split(";") if x.strip()]:
                c.execute(stmt)
            for table, cols in MIGRATIONS.items():
                for col, typ in cols.items():
                    c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}")
        return
    with conn() as c:
        c.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            for col, typ in cols.items():
                if col not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if USE_PG else sql


def _q(sql, args=()):
    with conn() as c:
        cur = c.execute(_sql(sql), args)
        return [dict(r) for r in cur.fetchall()]


def _one(sql, args=()):
    rows = _q(sql, args)
    return rows[0] if rows else None


def _x(sql, args=()):
    """Execute a write; returns the new row id for INSERTs."""
    with conn() as c:
        if USE_PG:
            is_insert = sql.lstrip().upper().startswith("INSERT")
            cur = c.execute(_sql(sql) + (" RETURNING id" if is_insert else ""), args)
            return cur.fetchone()["id"] if is_insert else None
        return c.execute(sql, args).lastrowid


# ---- users -----------------------------------------------------------------
def create_user(email, name, pw_hash):
    """The very first account becomes the admin."""
    first = _one("SELECT COUNT(*) n FROM users")["n"] == 0
    return _x("INSERT INTO users(email,name,pw_hash,role) VALUES(?,?,?,?)",
              (email.lower().strip(), name.strip(), pw_hash, "admin" if first else "user"))


def get_user_by_email(email):
    return _one("SELECT * FROM users WHERE email=?", (email.lower().strip(),))


def get_user(uid):
    u = _one("SELECT * FROM users WHERE id=?", (uid,))
    if u and u["plan"] != "free" and u["plan_expires"] and u["plan_expires"] < datetime.utcnow().isoformat():
        _x("UPDATE users SET plan='free', period=NULL, plan_expires=NULL WHERE id=?", (uid,))
        u = _one("SELECT * FROM users WHERE id=?", (uid,))
    return u


def list_users():
    return _q("SELECT id,email,name,role,plan,period,plan_expires,created_at FROM users ORDER BY id DESC")


def set_plan(uid, plan, period=None):
    exp = None
    if plan != "free":
        exp = (datetime.utcnow() + timedelta(days=366 if period == "yearly" else 31)).isoformat()
    _x("UPDATE users SET plan=?, period=?, plan_expires=? WHERE id=?", (plan, period, exp, uid))


def claim_login_alert(uid, min_minutes=10) -> bool:
    """True (and stamps now) if no login alert was sent to this user in the last `min_minutes`."""
    u = _one("SELECT last_alert FROM users WHERE id=?", (uid,))
    now = datetime.utcnow()
    if u and u["last_alert"] and u["last_alert"] > (now - timedelta(minutes=min_minutes)).isoformat(sep=" ", timespec="seconds"):
        return False
    _x("UPDATE users SET last_alert=? WHERE id=?", (now.isoformat(sep=" ", timespec="seconds"), uid))
    return True


def update_profile(uid, name, pw_hash=None):
    if pw_hash:
        _x("UPDATE users SET name=?, pw_hash=? WHERE id=?", (name, pw_hash, uid))
    else:
        _x("UPDATE users SET name=? WHERE id=?", (name, uid))


# ---- qr codes --------------------------------------------------------------
def _new_code():
    while True:
        code = secrets.token_urlsafe(5).replace("-", "a").replace("_", "b")[:7]
        if not _one("SELECT 1 FROM qrcodes WHERE short_code=?", (code,)):
            return code


def save_qr(uid, name, qr_type, content, style: dict, dynamic: bool, dest=None, campaign=None):
    code = _new_code() if dynamic else None
    return _x("INSERT INTO qrcodes(user_id,name,qr_type,content,is_dynamic,short_code,dest,style,campaign)"
              " VALUES(?,?,?,?,?,?,?,?,?)",
              (uid, name, qr_type, content, int(dynamic), code, dest, json.dumps(style), campaign or None))


def list_qrs(uid):
    rows = _q("SELECT q.*, (SELECT COUNT(*) FROM scans s WHERE s.qr_id=q.id) scans "
              "FROM qrcodes q WHERE user_id=? ORDER BY id DESC", (uid,))
    for r in rows:
        r["style"] = json.loads(r["style"] or "{}")
    return rows


def count_dynamic(uid):
    return _one("SELECT COUNT(*) n FROM qrcodes WHERE user_id=? AND is_dynamic=1", (uid,))["n"]


def get_qr_by_code(code):
    return _one("SELECT * FROM qrcodes WHERE short_code=?", (code,))


def update_qr(qid, uid, **fields):
    allowed = {"name", "dest", "active", "rules", "campaign", "trust_preview", "health", "health_at"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if sets:
        _x(f"UPDATE qrcodes SET {','.join(k + '=?' for k in sets)} WHERE id=? AND user_id=?",
           (*sets.values(), qid, uid))


def delete_qr(qid, uid):
    _x("DELETE FROM scans WHERE qr_id IN (SELECT id FROM qrcodes WHERE id=? AND user_id=?)", (qid, uid))
    _x("DELETE FROM qrcodes WHERE id=? AND user_id=?", (qid, uid))


# ---- scans -----------------------------------------------------------------
def log_scan(qr_id, device, os_, browser, lang=None, visitor=None, outcome="redirect", variant=None):
    _x("INSERT INTO scans(qr_id,ts,device,os,browser,lang,visitor,outcome,variant) VALUES(?,?,?,?,?,?,?,?,?)",
       (qr_id, datetime.utcnow().isoformat(sep=" ", timespec="seconds"), device, os_, browser, lang, visitor,
        outcome, variant))


def count_scans(qr_id):
    return _one("SELECT COUNT(*) n FROM scans WHERE qr_id=?", (qr_id,))["n"]


def add_report(qr_id, reason, note=""):
    _x("INSERT INTO reports(qr_id,reason,note) VALUES(?,?,?)", (qr_id, reason, note[:500]))


def list_reports():
    return _q("SELECT r.*, q.short_code, q.dest, q.active, u.email owner FROM reports r "
              "JOIN qrcodes q ON q.id=r.qr_id JOIN users u ON u.id=q.user_id ORDER BY r.id DESC")


def set_report_status(rid, status):
    _x("UPDATE reports SET status=? WHERE id=?", (status, rid))


def set_qr_active_admin(qid, active):
    _x("UPDATE qrcodes SET active=? WHERE id=?", (int(active), qid))


def scans_for_user(uid, days):
    since = (datetime.utcnow() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
    return _q("SELECT s.ts, s.device, s.os, s.browser, s.lang, s.visitor, s.outcome, s.variant, "
              "q.id qr_id, q.name qr_name, q.campaign "
              "FROM scans s JOIN qrcodes q ON q.id=s.qr_id WHERE q.user_id=? AND s.ts>=? ORDER BY s.ts",
              (uid, since))


# ---- payments / admin --------------------------------------------------------
def add_payment(uid, plan, period, amount, coupon, provider, status, txn_ref):
    return _x("INSERT INTO payments(user_id,plan,period,amount,coupon,provider,status,txn_ref)"
              " VALUES(?,?,?,?,?,?,?,?)", (uid, plan, period, amount, coupon, provider, status, txn_ref))


_PAY_COLS = "id,user_id,plan,period,amount,coupon,provider,status,txn_ref,pay_date,notes,reviewed_by,reviewed_at,created_at"


def payments_for_user(uid):
    return _q(f"SELECT {_PAY_COLS} FROM payments WHERE user_id=? ORDER BY id DESC", (uid,))


def all_payments():
    cols = ",".join("p." + c for c in _PAY_COLS.split(","))
    return _q(f"SELECT {cols}, u.email FROM payments p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC")


# ---- settings (e.g. the UPI payment QR image, stored base64) -------------------
def get_setting(key):
    return _one("SELECT value, mime FROM settings WHERE key=?", (key,))


def set_setting(key, value, mime=None):
    sql = ("INSERT INTO settings(key,value,mime,updated_at) VALUES(?,?,?,?) "
           "ON CONFLICT(key) DO UPDATE SET value=excluded.value, mime=excluded.mime, updated_at=excluded.updated_at")
    with conn() as c:
        c.execute(_sql(sql), (key, value, mime, datetime.utcnow().isoformat(sep=" ", timespec="seconds")))


# ---- manual UPI payment claims (user pays by UPI, uploads screenshot, admin approves) ----
def submit_claim(uid, plan, period, amount, coupon, pay_date, ref, notes, shot_b64, shot_mime):
    return _x("INSERT INTO payments(user_id,plan,period,amount,coupon,provider,status,txn_ref,pay_date,notes,screenshot,screenshot_mime)"
              " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (uid, plan, period, int(round(amount)), coupon, "upi_manual", "pending", ref or None, str(pay_date),
               notes or None, shot_b64, shot_mime))


def get_pending_claim(uid):
    return _one("SELECT id,plan,period,amount,created_at FROM payments WHERE user_id=? AND status='pending' "
                "ORDER BY id DESC LIMIT 1", (uid,))


def list_pending_claims():
    return _q("SELECT p.id,p.user_id,u.email,u.name,p.plan,p.period,p.amount,p.coupon,p.pay_date,p.txn_ref,p.notes,p.created_at "
              "FROM payments p JOIN users u ON u.id=p.user_id WHERE p.status='pending' ORDER BY p.id ASC")


def get_claim_screenshot(pid):
    return _one("SELECT screenshot, screenshot_mime FROM payments WHERE id=?", (pid,))


def approve_claim(pid, by):
    row = _one("SELECT user_id,plan,period FROM payments WHERE id=? AND status='pending'", (pid,))
    if not row:
        return None
    set_plan(row["user_id"], row["plan"], row["period"])
    _x("UPDATE payments SET status='paid', reviewed_by=?, reviewed_at=? WHERE id=?",
       (by, datetime.utcnow().isoformat(sep=" ", timespec="seconds"), pid))
    return row


def reject_claim(pid, by, reason=""):
    row = _one("SELECT user_id,plan,period FROM payments WHERE id=? AND status='pending'", (pid,))
    if not row:
        return None
    _x("UPDATE payments SET status='rejected', reviewed_by=?, reviewed_at=?, notes=? WHERE id=?",
       (by, datetime.utcnow().isoformat(sep=" ", timespec="seconds"), reason or None, pid))
    return row


def platform_stats():
    return {
        "users": _one("SELECT COUNT(*) n FROM users")["n"],
        "qrs": _one("SELECT COUNT(*) n FROM qrcodes")["n"],
        "scans": _one("SELECT COUNT(*) n FROM scans")["n"],
    }
