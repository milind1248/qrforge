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
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, qr_id INTEGER NOT NULL, reason TEXT, note TEXT,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

MIGRATIONS = {  # table -> {column: type}; keeps older local databases working
    "qrcodes": {"rules": "TEXT", "campaign": "TEXT", "trust_preview": "INTEGER DEFAULT 0",
                "health": "TEXT", "health_at": "TEXT"},
    "scans": {"lang": "TEXT", "visitor": "TEXT", "outcome": "TEXT", "variant": "TEXT"},
}


PG_TS = "to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')"


def _pg_schema() -> str:
    """Same tables as SCHEMA, in Postgres dialect. Timestamps stay TEXT so the app code is backend-neutral."""
    t = (SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
         .replace("DEFAULT CURRENT_TIMESTAMP", f"DEFAULT ({PG_TS})"))
    tables = ["users", "qrcodes", "scans", "payments", "reports"]
    rls = "".join(f"ALTER TABLE {n} ENABLE ROW LEVEL SECURITY;" for n in tables)  # block the public anon API
    return t + rls


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=4, open=True,
                               kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": False})
    return _pool


@contextmanager
def conn():
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


def init_db():
    if USE_PG:
        with conn() as c:
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


def payments_for_user(uid):
    return _q("SELECT * FROM payments WHERE user_id=? ORDER BY id DESC", (uid,))


def all_payments():
    return _q("SELECT p.*, u.email FROM payments p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC")


def platform_stats():
    return {
        "users": _one("SELECT COUNT(*) n FROM users")["n"],
        "qrs": _one("SELECT COUNT(*) n FROM qrcodes")["n"],
        "scans": _one("SELECT COUNT(*) n FROM scans")["n"],
    }
