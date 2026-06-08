"""SQLite(WAL) 스키마 생성·적재 — 구현가이드 §6.

절대 규칙 6: DB는 **기록 전용**이다. 컴포넌트 간 통신 수단으로 쓰지 않는다.
모든 실시간 흐름은 MQTT, DB는 결과 적재(블랙박스/증빙/관제 이력)만 담당.

용도(가이드 §6):
- 통합 디버깅 블랙박스
- 핸드오버 3초 증빙(missions.handover_latency_ms) — 수락 기준
- 관제 이력 / FMS 재시작 시 미완료 mission 발견 → 안전 복귀
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

import config


# 단일 연결을 여러 스레드(MQTT 콜백 / Flask / 타임아웃 감시)가 공유.
# WAL은 다중 reader + 단일 writer를 허용하므로, write 직렬화를 위해 Lock을 둔다.
_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    request_id   TEXT PRIMARY KEY,
    robot_id     TEXT,
    request_type TEXT,
    payload_json TEXT,
    received_at  TEXT
);

CREATE TABLE IF NOT EXISTS missions (
    mission_id          TEXT PRIMARY KEY,
    request_id          TEXT,
    state               TEXT,
    start_robot         TEXT,
    next_robot          TEXT,
    dest_poi            TEXT,
    customer_profile    TEXT,
    language            TEXT,
    created_at          TEXT,
    completed_at        TEXT,
    handover_latency_ms INTEGER
);

CREATE TABLE IF NOT EXISTS mission_transitions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT,
    from_state TEXT,
    to_state   TEXT,
    trigger    TEXT,
    at         TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    mission_id   TEXT,
    robot_id     TEXT,
    task_type    TEXT,
    goal_poi     TEXT,
    issued_at    TEXT,
    ack          TEXT,
    ack_at       TEXT,
    final_status TEXT,
    finished_at  TEXT
);

-- 전이/변화 시에만 INSERT (1~2Hz 주기 보고는 robot_registry의 메모리 최신값만)
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
    event_type   TEXT,
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

CREATE INDEX IF NOT EXISTS idx_missions_created   ON missions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transitions_mid    ON mission_transitions(mission_id);
CREATE INDEX IF NOT EXISTS idx_tasks_mid          ON tasks(mission_id);
CREATE INDEX IF NOT EXISTS idx_status_log_robot   ON robot_status_log(robot_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_events_at          ON events(at DESC);
"""


def utc_now_iso() -> str:
    """ISO 8601(ms 포함, UTC). 공통 timestamp 형식 — NTP 동기화 전제."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """연결 생성 + WAL 활성화 + 스키마 보장. 멱등(재호출 안전)."""
    global _conn
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    _conn = conn
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB에 누락 컬럼 보강(멱등). CREATE TABLE IF NOT EXISTS 는 컬럼 추가 안 함."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(missions)")}
    if "language" not in cols:
        conn.execute("ALTER TABLE missions ADD COLUMN language TEXT")
    ecols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    if "resolved" not in ecols:
        conn.execute("ALTER TABLE events ADD COLUMN resolved INTEGER DEFAULT 0")
    if "resolved_at" not in ecols:
        conn.execute("ALTER TABLE events ADD COLUMN resolved_at TEXT")
    if "resolved_by" not in ecols:
        conn.execute("ALTER TABLE events ADD COLUMN resolved_by TEXT")


def get_conn() -> sqlite3.Connection:
    if _conn is None:
        return init_db()
    return _conn


def execute(sql: str, params: tuple = ()) -> None:
    """쓰기(INSERT/UPDATE). write 직렬화를 위해 Lock 보호."""
    conn = get_conn()
    with _lock:
        conn.execute(sql, params)
        conn.commit()


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """읽기 — Flask 조회 API용. Row → dict 변환."""
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
    print(f"FMS SQLite initialized (WAL): {config.DB_PATH}")
