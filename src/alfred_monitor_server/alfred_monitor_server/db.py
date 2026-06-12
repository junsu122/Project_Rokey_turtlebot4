"""SQLite storage for the monitoring server.

The database stores observations only: robot status changes, detector events,
and future UI/operator usage counters. It is not used as a command queue.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from . import config


_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS latest_robot_status (
    robot_id        TEXT PRIMARY KEY,
    floor           INTEGER,
    state           TEXT,
    battery         INTEGER,
    x               REAL,
    y               REAL,
    theta           REAL,
    current_task_id TEXT,
    task_status     TEXT,
    error_code      TEXT,
    last_seen       TEXT
);

CREATE TABLE IF NOT EXISTS robot_status_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id    TEXT,
    state       TEXT,
    prev_state  TEXT,
    task_id     TEXT,
    task_status TEXT,
    battery     INTEGER,
    x           REAL,
    y           REAL,
    at          TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id       TEXT,
    event_type   TEXT,
    event_class  TEXT,
    robot_id     TEXT,
    confidence   REAL,
    x            REAL,
    y            REAL,
    floor        INTEGER,
    snapshot_ref TEXT,
    at           TEXT,
    resolved     INTEGER DEFAULT 0,
    resolved_at  TEXT,
    resolved_by  TEXT
);

CREATE TABLE IF NOT EXISTS ui_usage_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT,
    language         TEXT,
    customer_profile TEXT,
    escort_used      INTEGER DEFAULT 0,
    at               TEXT
);

CREATE TABLE IF NOT EXISTS monitor_counters (
    name       TEXT PRIMARY KEY,
    value      INTEGER DEFAULT 0,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_status_log_robot ON robot_status_log(robot_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_latest_robot_floor ON latest_robot_status(floor);
CREATE INDEX IF NOT EXISTS idx_events_at        ON events(at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_at         ON ui_usage_log(at DESC);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, event_class);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    global _conn
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.executescript(INDEXES)
    conn.commit()
    _conn = conn
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    event_cols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    for name, ddl in {
        "msg_id": "ALTER TABLE events ADD COLUMN msg_id TEXT",
        "event_class": "ALTER TABLE events ADD COLUMN event_class TEXT",
        "resolved": "ALTER TABLE events ADD COLUMN resolved INTEGER DEFAULT 0",
        "resolved_at": "ALTER TABLE events ADD COLUMN resolved_at TEXT",
        "resolved_by": "ALTER TABLE events ADD COLUMN resolved_by TEXT",
    }.items():
        if name not in event_cols:
            conn.execute(ddl)


def get_conn() -> sqlite3.Connection:
    if _conn is None:
        return init_db()
    return _conn


def execute(sql: str, params: tuple = ()) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(sql, params)
        conn.commit()


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_conn()
    with _lock:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def close() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


if __name__ == "__main__":
    init_db()
    print(f"Monitoring SQLite initialized (WAL): {config.DB_PATH}")
