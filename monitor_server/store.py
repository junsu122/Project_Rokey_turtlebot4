"""Storage backend abstraction for the monitoring bridge.

Two backends selected by FMS_BACKEND:
  * ``sqlite``   - existing local SQLite via db.py (default)
  * ``supabase`` - PostgREST write pump to a Supabase project

Only the ROS2 ingest writers (robot_registry / event_service / usage_service)
use this module. With the supabase backend the external dashboard reads straight
from Supabase, so this side is write-only apart from ``get_prev_status`` which is
needed for robot_status_log change detection.

The supabase backend uses stdlib urllib (no extra dependency) and the
service_role key, which bypasses RLS.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import config

logger = logging.getLogger("monitor.store")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ---------------------------------------------------------------------------
# SQLite backend (default) — wraps the existing db.py
# ---------------------------------------------------------------------------
class SqliteStore:
    backend = "sqlite"

    def init(self) -> None:
        import db
        db.init_db()
        logger.info("store backend=sqlite path=%s", config.DB_PATH)

    def close(self) -> None:
        import db
        db.close()

    def get_prev_status(self, robot_id: str) -> dict | None:
        import db
        return db.query_one(
            "SELECT state, task_status FROM latest_robot_status WHERE robot_id=?",
            (robot_id,),
        )

    def upsert_robot_status(self, rec: dict) -> None:
        import db
        db.execute(
            "INSERT INTO latest_robot_status"
            "(robot_id, floor, state, battery, x, y, theta, current_task_id, "
            "task_status, error_code, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(robot_id) DO UPDATE SET "
            "floor=excluded.floor, state=excluded.state, battery=excluded.battery, "
            "x=excluded.x, y=excluded.y, theta=excluded.theta, "
            "current_task_id=excluded.current_task_id, task_status=excluded.task_status, "
            "error_code=excluded.error_code, last_seen=excluded.last_seen",
            (rec["robot_id"], rec["floor"], rec["state"], rec["battery"],
             rec["x"], rec["y"], rec["theta"], rec["current_task_id"],
             rec["task_status"], rec["error_code"], rec["last_seen"]),
        )

    def append_status_log(self, rec: dict) -> None:
        import db
        db.execute(
            "INSERT INTO robot_status_log"
            "(robot_id, state, prev_state, task_id, task_status, battery, x, y, at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rec["robot_id"], rec["state"], rec["prev_state"], rec["task_id"],
             rec["task_status"], rec["battery"], rec["x"], rec["y"], rec["at"]),
        )

    def insert_event(self, rec: dict) -> None:
        import db
        db.execute(
            "INSERT INTO events(msg_id, event_type, event_class, robot_id, confidence, "
            "x, y, floor, snapshot_ref, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rec["msg_id"], rec["event_type"], rec["event_class"], rec["robot_id"],
             rec["confidence"], rec["x"], rec["y"], rec["floor"],
             rec["snapshot_ref"], rec["at"]),
        )

    def insert_usage(self, rec: dict) -> None:
        import db
        db.execute(
            "INSERT INTO ui_usage_log(source, language, customer_profile, escort_used, at) "
            "VALUES (?, ?, ?, ?, ?)",
            (rec["source"], rec["language"], rec["customer_profile"],
             rec["escort_used"], rec["at"]),
        )


# ---------------------------------------------------------------------------
# Supabase backend — PostgREST write pump (stdlib urllib)
# ---------------------------------------------------------------------------
class SupabaseStore:
    backend = "supabase"

    def __init__(self) -> None:
        self.url = config.SUPABASE_URL.rstrip("/")
        self.key = config.SUPABASE_SERVICE_KEY
        self.rest = f"{self.url}/rest/v1"

    def init(self) -> None:
        if not self.url or not self.key:
            raise RuntimeError(
                "FMS_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_KEY")
        logger.info("store backend=supabase url=%s", self.url)

    def close(self) -> None:
        pass

    def _request(self, method: str, path: str, *, body=None, prefer: str | None = None):
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            f"{self.rest}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=config.SUPABASE_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            logger.error("supabase %s %s -> %s %s", method, path, e.code, detail)
            raise
        except urllib.error.URLError as e:
            logger.error("supabase %s %s unreachable: %s", method, path, e.reason)
            raise

    def get_prev_status(self, robot_id: str) -> dict | None:
        rows = self._request(
            "GET",
            f"/latest_robot_status?robot_id=eq.{robot_id}&select=state,task_status",
        )
        return rows[0] if rows else None

    def upsert_robot_status(self, rec: dict) -> None:
        self._request(
            "POST", "/latest_robot_status?on_conflict=robot_id",
            body=rec, prefer="resolution=merge-duplicates,return=minimal")

    def append_status_log(self, rec: dict) -> None:
        self._request("POST", "/robot_status_log", body=rec, prefer="return=minimal")

    def insert_event(self, rec: dict) -> None:
        self._request("POST", "/events", body=rec, prefer="return=minimal")

    def insert_usage(self, rec: dict) -> None:
        self._request("POST", "/ui_usage_log", body=rec, prefer="return=minimal")

    # ---- Event read/resolve (Option A: events are single-sourced in Supabase) ----
    def list_events(self, limit: int = 50, active: bool = False) -> list[dict]:
        q = f"/events?select=*&order=at.desc&limit={int(limit)}"
        if active:
            q += "&resolved=eq.0"
        return self._request("GET", q) or []

    def resolve_event(self, event_id: int, by: str = "operator") -> dict:
        rows = self._request("GET", f"/events?id=eq.{int(event_id)}&select=id,resolved")
        if not rows:
            return {"error": "event not found"}
        if rows[0].get("resolved"):
            return {"ok": True, "already": True}
        self._request(
            "PATCH", f"/events?id=eq.{int(event_id)}",
            body={"resolved": 1, "resolved_at": utc_now(), "resolved_by": by},
            prefer="return=minimal")
        return {"ok": True, "event_id": event_id, "resolved_by": by}

    def event_stats(self) -> dict:
        rows = self._request("GET", "/events?select=event_type,event_class,resolved") or []
        by_type: dict[str, int] = {}
        by_class: dict[str, int] = {}
        active = 0
        for r in rows:
            if not r.get("resolved"):
                active += 1
            t = r.get("event_type") or "UNKNOWN"
            by_type[t] = by_type.get(t, 0) + 1
            c = r.get("event_class")
            if c:
                by_class[c] = by_class.get(c, 0) + 1
        return {"total": len(rows), "active": active, "by_type": by_type, "by_class": by_class}


# ---------------------------------------------------------------------------
# Module-level dispatch
# ---------------------------------------------------------------------------
_backend: SqliteStore | SupabaseStore | None = None


def get_backend():
    global _backend
    if _backend is None:
        if config.BACKEND == "supabase":
            _backend = SupabaseStore()
        else:
            _backend = SqliteStore()
    return _backend


def init() -> None:
    get_backend().init()


def close() -> None:
    if _backend is not None:
        _backend.close()


def get_prev_status(robot_id: str) -> dict | None:
    return get_backend().get_prev_status(robot_id)


def upsert_robot_status(rec: dict) -> None:
    get_backend().upsert_robot_status(rec)


def append_status_log(rec: dict) -> None:
    get_backend().append_status_log(rec)


def insert_event(rec: dict) -> None:
    get_backend().insert_event(rec)


def insert_usage(rec: dict) -> None:
    get_backend().insert_usage(rec)
