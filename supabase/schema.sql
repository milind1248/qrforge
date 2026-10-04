-- Optional: the app creates these tables itself on first start.
-- Run this in Supabase SQL editor if you prefer to create them manually.
CREATE TABLE IF NOT EXISTS users(
  id BIGSERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT,
  pw_hash TEXT NOT NULL, role TEXT DEFAULT 'user', plan TEXT DEFAULT 'free',
  period TEXT, plan_expires TEXT, created_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')));
CREATE TABLE IF NOT EXISTS qrcodes(
  id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT, qr_type TEXT,
  content TEXT, is_dynamic INTEGER DEFAULT 0, short_code TEXT UNIQUE, dest TEXT,
  style TEXT, active INTEGER DEFAULT 1, created_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')),
  rules TEXT, campaign TEXT, trust_preview INTEGER DEFAULT 0, health TEXT, health_at TEXT);
CREATE TABLE IF NOT EXISTS scans(
  id BIGSERIAL PRIMARY KEY, qr_id INTEGER NOT NULL, ts TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')),
  device TEXT, os TEXT, browser TEXT, lang TEXT, visitor TEXT, outcome TEXT, variant TEXT);
CREATE INDEX IF NOT EXISTS ix_scans_qr ON scans(qr_id, ts);
CREATE TABLE IF NOT EXISTS payments(
  id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL, plan TEXT, period TEXT,
  amount INTEGER, coupon TEXT, provider TEXT, status TEXT, txn_ref TEXT,
  created_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')));
CREATE TABLE IF NOT EXISTS reports(
  id BIGSERIAL PRIMARY KEY, qr_id INTEGER NOT NULL, reason TEXT, note TEXT,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD HH24:MI:SS')));
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE qrcodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
