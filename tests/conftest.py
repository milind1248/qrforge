"""Test isolation: never touch the real database or send real email, whatever secrets exist on this machine.
Default: SQLite in a temp folder. Set QRFORGE_TEST_PG=postgresql://...@localhost:PORT/db to run the same suite on a LOCAL Postgres
(refused for any non-local host, so production can never be hit)."""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

TEST_PG = os.environ.get("QRFORGE_TEST_PG", "")
if TEST_PG:
    if urlparse(TEST_PG).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit("QRFORGE_TEST_PG must point at a local database")
else:
    os.environ["QRFORGE_FORCE_SQLITE"] = "1"   # never the production database (see core/config.py)
os.environ["QRFORGE_NO_EMAIL"] = "1"           # never send real email
os.environ.setdefault("LICENSE_KEY", "99c4c580dc45642bcc2593c5ff63a16108fa0a64bdce8533db94b6eba6d48003")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    from core import db
    if TEST_PG:
        assert db.USE_PG and urlparse(db.DATABASE_URL).hostname in ("localhost", "127.0.0.1", "::1"), "refusing to run: not a local Postgres"
        with db._get_pool().connection() as c:
            c.execute(f"DROP SCHEMA IF EXISTS {db.PG_SCHEMA} CASCADE")
        db.init_db()
        return db
    assert not db.USE_PG, "tests must run on SQLite"
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db
