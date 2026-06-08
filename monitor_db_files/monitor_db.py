"""SQLite storage for the standalone monitoring UI.

This module is intentionally independent from fms_server.  It stores the data
that the 3D UI needs when the project is used as monitoring-only:

- latest robot pose/state for map markers
- robot status history for trails/debugging
- mission/request summary
- monitoring events for counters and alerts
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("MONITOR_DB_PATH", str(BASE_DIR / "data" / "monitor.db")))
SCHEMA_VERSION = "monitor-1.0"

LANGUAGES = ("ko", "zh", "ja", "en")
THREAT_TYPES = ("gun", "knife")

EVENT_USER_INTERACTION = "USER_INTERACTION"
EVENT_TRANSPORTATION_WEAK = "TRANSPORTATION_WEAK"
EVENT_ESCORT_STARTED = "ESCORT_STARTED"
EVENT_ESCORT_COMPLETED = "ESCORT_COMPLETED"
EVENT_FIRE_DETECTED = "FIRE_DETECTED"
EVENT_EMERGENCY_PATIENT = "EMERGENCY_PATIENT"
EVENT_THREAT_DETECTED = "THREAT_DETECTED"
EVENT_EMERGENCY_ACTION = "EMERGENCY_ACTION"
EVENT_LOST_ITEM = "LOST_ITEM"


_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS robots (
    robot_id   TEXT PRIMARY KEY,
    robot_name TEXT,
    floor      INTEGER,
    zone       TEXT,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS robot_status_latest (
    robot_id         TEXT PRIMARY KEY,
    state            TEXT,
    mission_state    TEXT,
    task_status      TEXT,
    current_task_id  TEXT,
    mission_id       TEXT,
    role             TEXT,
    floor            INTEGER,
    x                REAL,
    y                REAL,
    theta            REAL,
    battery          REAL,
    error_code       TEXT,
    online           INTEGER NOT NULL DEFAULT 1,
    last_seen        TEXT NOT NULL,
    raw_json         TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS robot_status_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id         TEXT NOT NULL,
    state            TEXT,
    mission_state    TEXT,
    task_status      TEXT,
    current_task_id  TEXT,
    mission_id       TEXT,
    role             TEXT,
    floor            INTEGER,
    x                REAL,
    y                REAL,
    theta            REAL,
    battery          REAL,
    error_code       TEXT,
    at               TEXT NOT NULL,
    raw_json         TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS missions (
    mission_id              TEXT PRIMARY KEY,
    mission_type            TEXT NOT NULL DEFAULT 'ESCORT',
    state                   TEXT,
    request_robot_id        TEXT,
    start_robot_id          TEXT,
    next_robot_id           TEXT,
    destination_id          TEXT,
    customer_language       TEXT,
    is_transportation_weak  INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    completed_at            TEXT,
    raw_json                TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS mission_state_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  TEXT NOT NULL,
    state       TEXT,
    robot_id    TEXT,
    event_type  TEXT,
    at          TEXT NOT NULL,
    raw_json    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS monitor_events (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    source_id    TEXT,
    robot_id     TEXT,
    mission_id   TEXT,
    language     TEXT,
    count        INTEGER NOT NULL DEFAULT 1,
    detection_class TEXT,
    threat_type  TEXT,
    action_type  TEXT,
    floor        INTEGER,
    zone         TEXT,
    location_name TEXT,
    x            REAL,
    y            REAL,
    confidence   REAL,
    snapshot_ref TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_robot_status_latest_last_seen
    ON robot_status_latest(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_robot_status_log_robot_at
    ON robot_status_log(robot_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_missions_state_updated
    ON missions(state, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_mission_state_log_mission_at
    ON mission_state_log(mission_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_events_type_at
    ON monitor_events(event_type, at DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_events_robot_at
    ON monitor_events(robot_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_events_mission_at
    ON monitor_events(mission_id, at DESC);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def _json_loads(value: str | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    global _conn
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO schema_meta(key, value, updated_at)
        VALUES('schema_version', ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (SCHEMA_VERSION, now),
    )
    conn.commit()
    _conn = conn
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add columns when an older monitor.db already exists."""
    wanted = {
        "robot_status_latest": {
            "mission_state": "TEXT",
            "role": "TEXT",
        },
        "robot_status_log": {
            "mission_state": "TEXT",
            "role": "TEXT",
        },
        "monitor_events": {
            "zone": "TEXT",
            "location_name": "TEXT",
            "detection_class": "TEXT",
        },
    }
    for table, columns in wanted.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, column_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


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
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def seed_default_robots() -> None:
    now = utc_now_iso()
    for robot_id, floor in (("robot2", 1), ("robot4", 2)):
        execute(
            """
            INSERT INTO robots(robot_id, robot_name, floor, is_active, created_at, updated_at)
            VALUES(?, ?, ?, 1, ?, ?)
            ON CONFLICT(robot_id) DO UPDATE SET
                robot_name = excluded.robot_name,
                floor = excluded.floor,
                is_active = 1,
                updated_at = excluded.updated_at
            """,
            (robot_id, robot_id, floor, now, now),
        )


def record_robot_status(payload: dict) -> None:
    robot_id = payload.get("robot_id")
    if not robot_id:
        raise ValueError("robot_id is required")

    pose = payload.get("pose") or payload.get("location") or {}
    if isinstance(payload.get("location"), dict) and isinstance(payload["location"].get("pose"), dict):
        pose = payload["location"]["pose"]

    at = payload.get("timestamp") or payload.get("last_seen") or utc_now_iso()
    state = payload.get("state") or payload.get("robot_state")
    mission_state = payload.get("mission_state")
    task_status = payload.get("task_status")
    task_id = payload.get("current_task_id") or payload.get("task_id")
    mission_id = payload.get("mission_id")
    role = payload.get("role")
    floor = _first_not_none(payload.get("floor"), (payload.get("location") or {}).get("floor"))
    x = pose.get("x")
    y = pose.get("y")
    theta = _first_not_none(pose.get("theta"), pose.get("yaw"))
    battery = payload.get("battery")
    error_code = payload.get("error_code")
    raw_json = _json_dumps(payload)

    execute(
        """
        INSERT INTO robots(robot_id, robot_name, floor, is_active, created_at, updated_at)
        VALUES(?, ?, ?, 1, ?, ?)
        ON CONFLICT(robot_id) DO UPDATE SET
            floor = COALESCE(excluded.floor, robots.floor),
            is_active = 1,
            updated_at = excluded.updated_at
        """,
        (robot_id, payload.get("robot_name") or robot_id, floor, at, at),
    )
    execute(
        """
        INSERT INTO robot_status_latest(
            robot_id, state, mission_state, task_status, current_task_id, mission_id, role, floor,
            x, y, theta, battery, error_code, online, last_seen, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(robot_id) DO UPDATE SET
            state = excluded.state,
            mission_state = COALESCE(excluded.mission_state, robot_status_latest.mission_state),
            task_status = excluded.task_status,
            current_task_id = excluded.current_task_id,
            mission_id = COALESCE(excluded.mission_id, robot_status_latest.mission_id),
            role = COALESCE(excluded.role, robot_status_latest.role),
            floor = excluded.floor,
            x = excluded.x,
            y = excluded.y,
            theta = excluded.theta,
            battery = excluded.battery,
            error_code = excluded.error_code,
            online = 1,
            last_seen = excluded.last_seen,
            raw_json = excluded.raw_json
        """,
        (
            robot_id,
            state,
            mission_state,
            task_status,
            task_id,
            mission_id,
            role,
            floor,
            x,
            y,
            theta,
            battery,
            error_code,
            at,
            raw_json,
        ),
    )
    execute(
        """
        INSERT INTO robot_status_log(
            robot_id, state, mission_state, task_status, current_task_id, mission_id, role, floor,
            x, y, theta, battery, error_code, at, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            robot_id,
            state,
            mission_state,
            task_status,
            task_id,
            mission_id,
            role,
            floor,
            x,
            y,
            theta,
            battery,
            error_code,
            at,
            raw_json,
        ),
    )


def update_robot_mission(
    robot_id: str,
    mission_id: str | None,
    mission_state: str | None,
    role: str | None = None,
    at: str | None = None,
) -> None:
    if not robot_id:
        return
    now = at or utc_now_iso()
    execute(
        """
        INSERT INTO robots(robot_id, robot_name, is_active, created_at, updated_at)
        VALUES(?, ?, 1, ?, ?)
        ON CONFLICT(robot_id) DO UPDATE SET
            is_active = 1,
            updated_at = excluded.updated_at
        """,
        (robot_id, robot_id, now, now),
    )
    execute(
        """
        INSERT INTO robot_status_latest(
            robot_id, mission_state, mission_id, role, online, last_seen, raw_json
        )
        VALUES (?, ?, ?, ?, 1, ?, '{}')
        ON CONFLICT(robot_id) DO UPDATE SET
            mission_state = COALESCE(excluded.mission_state, robot_status_latest.mission_state),
            mission_id = COALESCE(excluded.mission_id, robot_status_latest.mission_id),
            role = COALESCE(excluded.role, robot_status_latest.role),
            last_seen = excluded.last_seen
        """,
        (robot_id, mission_state, mission_id, role, now),
    )


def upsert_mission(payload: dict) -> None:
    mission_id = payload.get("mission_id")
    if not mission_id:
        raise ValueError("mission_id is required")

    customer = payload.get("customer") or payload.get("customer_profile") or {}
    robots = payload.get("robots") or {}
    now = utc_now_iso()
    mission_state = payload.get("mission_state") or payload.get("state")
    is_request_payload = bool(payload.get("request_type") or payload.get("destination_id") or payload.get("destination"))
    request_robot_id = (
        payload.get("request_robot_id")
        or payload.get("request_robot")
        or (payload.get("robot_id") if is_request_payload else None)
    )
    start_robot_id = payload.get("start_robot_id") or payload.get("start_robot") or robots.get("start_robot")
    next_robot_id = payload.get("next_robot_id") or payload.get("next_robot") or robots.get("next_robot")
    execute(
        """
        INSERT INTO missions(
            mission_id, mission_type, state, request_robot_id, start_robot_id,
            next_robot_id, destination_id, customer_language, is_transportation_weak,
            created_at, updated_at, completed_at, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mission_id) DO UPDATE SET
            mission_type = COALESCE(excluded.mission_type, missions.mission_type),
            state = COALESCE(excluded.state, missions.state),
            request_robot_id = COALESCE(excluded.request_robot_id, missions.request_robot_id),
            start_robot_id = COALESCE(excluded.start_robot_id, missions.start_robot_id),
            next_robot_id = COALESCE(excluded.next_robot_id, missions.next_robot_id),
            destination_id = COALESCE(excluded.destination_id, missions.destination_id),
            customer_language = COALESCE(excluded.customer_language, missions.customer_language),
            is_transportation_weak = MAX(excluded.is_transportation_weak, missions.is_transportation_weak),
            updated_at = excluded.updated_at,
            completed_at = COALESCE(excluded.completed_at, missions.completed_at),
            raw_json = excluded.raw_json
        """,
        (
            mission_id,
            payload.get("mission_type") or payload.get("request_type") or "ESCORT",
            mission_state,
            request_robot_id,
            start_robot_id,
            next_robot_id,
            payload.get("destination_id") or payload.get("dest_poi"),
            payload.get("language") or customer.get("language"),
            int(bool(payload.get("is_transportation_weak") or customer.get("transportation_weak"))),
            payload.get("created_at") or payload.get("timestamp") or now,
            now,
            payload.get("completed_at"),
            _json_dumps(payload),
        ),
    )
    if mission_state:
        execute(
            """
            INSERT INTO mission_state_log(mission_id, state, robot_id, event_type, at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                mission_id,
                mission_state,
                payload.get("robot_id"),
                payload.get("event_type"),
                payload.get("timestamp") or now,
                _json_dumps(payload),
            ),
        )
        execute(
            """
            UPDATE robot_status_latest
            SET mission_state = ?
            WHERE mission_id = ?
            """,
            (mission_state, mission_id),
        )

    if payload.get("robot_id"):
        update_robot_mission(payload.get("robot_id"), mission_id, mission_state, payload.get("role"), payload.get("timestamp"))
    if request_robot_id:
        update_robot_mission(request_robot_id, mission_id, mission_state, payload.get("role"), payload.get("timestamp"))
    if start_robot_id:
        update_robot_mission(start_robot_id, mission_id, mission_state, "start", payload.get("timestamp"))
    if next_robot_id:
        update_robot_mission(next_robot_id, mission_id, mission_state, "next", payload.get("timestamp"))


def record_monitor_event(
    event_type: str,
    source_type: str,
    source_id: str | None = None,
    robot_id: str | None = None,
    mission_id: str | None = None,
    language: str | None = None,
    count: int = 1,
    detection_class: str | None = None,
    threat_type: str | None = None,
    action_type: str | None = None,
    floor: int | None = None,
    zone: str | None = None,
    location_name: str | None = None,
    x: float | None = None,
    y: float | None = None,
    confidence: float | None = None,
    snapshot_ref: str | None = None,
    payload: dict | None = None,
    at: str | None = None,
) -> str:
    event_id = f"MEVT_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    execute(
        """
        INSERT INTO monitor_events(
            event_id, event_type, source_type, source_id, robot_id, mission_id,
            language, count, detection_class, threat_type, action_type, floor, zone,
            location_name, x, y, confidence, snapshot_ref, payload_json, at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            source_type,
            source_id,
            robot_id,
            mission_id,
            language,
            count,
            detection_class,
            threat_type,
            action_type,
            floor,
            zone,
            location_name,
            x,
            y,
            confidence,
            snapshot_ref,
            _json_dumps(payload),
            at or utc_now_iso(),
        ),
    )
    return event_id


def list_latest_robots() -> list[dict]:
    return query_all(
        """
        SELECT r.robot_id, r.state, r.mission_state, r.task_status, r.current_task_id,
               r.mission_id, r.role, r.floor, r.x, r.y, r.theta, r.battery,
               r.error_code, r.online, r.last_seen,
               m.state AS mission_table_state,
               m.destination_id,
               m.start_robot_id,
               m.next_robot_id
        FROM robot_status_latest r
        LEFT JOIN missions m ON m.mission_id = r.mission_id
        ORDER BY r.robot_id
        """
    )


def list_active_missions() -> list[dict]:
    return query_all(
        """
        SELECT *
        FROM missions
        WHERE state IS NULL
           OR state NOT IN ('COMPLETED', 'CANCELLED', 'EMERGENCY', 'FAILED')
        ORDER BY updated_at DESC
        """
    )


def list_recent_events(limit: int = 100) -> list[dict]:
    rows = query_all(
        "SELECT * FROM monitor_events ORDER BY at DESC LIMIT ?",
        (limit,),
    )
    for row in rows:
        row["payload"] = _json_loads(row.pop("payload_json", "{}"))
    return rows


def monitor_stats() -> dict:
    def count(event_type: str) -> int:
        row = query_one(
            "SELECT COALESCE(SUM(count), 0) AS c FROM monitor_events WHERE event_type=?",
            (event_type,),
        )
        return int(row["c"] if row else 0)

    language_counts = {lang: 0 for lang in LANGUAGES}
    for row in query_all(
        """
        SELECT language, COALESCE(SUM(count), 0) AS c
        FROM monitor_events
        WHERE event_type=? AND language IS NOT NULL
        GROUP BY language
        """,
        (EVENT_USER_INTERACTION,),
    ):
        if row["language"] in language_counts:
            language_counts[row["language"]] = int(row["c"])

    threat_counts = {threat_type: 0 for threat_type in THREAT_TYPES}
    for row in query_all(
        """
        SELECT threat_type, COALESCE(SUM(count), 0) AS c
        FROM monitor_events
        WHERE event_type=? AND threat_type IS NOT NULL
        GROUP BY threat_type
        """,
        (EVENT_THREAT_DETECTED,),
    ):
        if row["threat_type"] in threat_counts:
            threat_counts[row["threat_type"]] = int(row["c"])

    return {
        "user_count": count(EVENT_USER_INTERACTION),
        "language_counts": language_counts,
        "transportation_weak_count": count(EVENT_TRANSPORTATION_WEAK),
        "escort": {
            "started_count": count(EVENT_ESCORT_STARTED),
            "completed_count": count(EVENT_ESCORT_COMPLETED),
        },
        "fire_count": count(EVENT_FIRE_DETECTED),
        "emergency_patient_count": count(EVENT_EMERGENCY_PATIENT),
        "lost_item_count": count(EVENT_LOST_ITEM),
        "threat": {
            "total_count": threat_counts["gun"] + threat_counts["knife"],
            "gun_count": threat_counts["gun"],
            "knife_count": threat_counts["knife"],
            "emergency_action_count": count(EVENT_EMERGENCY_ACTION),
        },
    }


def clear_logs(keep_latest: bool = True) -> None:
    """Clear accumulated logs/counters.

    keep_latest=True keeps robot_status_latest and robots so the UI can still
    show the last known robot card.  It clears event counters, history logs,
    missions, and mission transition history.
    """
    for table in ("monitor_events", "mission_state_log", "robot_status_log", "missions"):
        execute(f"DELETE FROM {table}")
    if not keep_latest:
        execute("DELETE FROM robot_status_latest")


def reset_all() -> None:
    """Clear all runtime data and seed the default robot rows again."""
    for table in (
        "monitor_events",
        "mission_state_log",
        "robot_status_log",
        "robot_status_latest",
        "missions",
        "robots",
    ):
        execute(f"DELETE FROM {table}")
    seed_default_robots()


def close() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize or clear the viz_3d monitor SQLite DB.")
    parser.add_argument("--clear-logs", action="store_true", help="clear events/logs/missions but keep latest robot state")
    parser.add_argument("--clear-latest", action="store_true", help="with --clear-logs, also clear latest robot state")
    parser.add_argument("--reset-all", action="store_true", help="clear all runtime rows and reseed default robots")
    args = parser.parse_args()

    init_db()
    seed_default_robots()
    if args.reset_all:
        reset_all()
        print(f"monitor DB reset all: {DB_PATH}")
    elif args.clear_logs:
        clear_logs(keep_latest=not args.clear_latest)
        print(f"monitor DB logs cleared: {DB_PATH}")
    else:
        print(f"monitor DB initialized: {DB_PATH}")
