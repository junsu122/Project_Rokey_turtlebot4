"""Read-only Flask API for the monitoring dashboard."""

from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

from . import config
from . import db
from .store import SupabaseStore


logger = logging.getLogger("monitor.api")

# Option A: when Supabase is configured, the local dashboard sources EVENTS from
# Supabase (single source of truth) so resolve syncs with the security team's
# external view. Robot status / usage stay on local SQLite.
_sb_events: SupabaseStore | None = None
if config.SUPABASE_URL:
    try:
        _sb_events = SupabaseStore()
        _sb_events.init()
        logger.info("events sourced from Supabase (resolve syncs with external UI)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase events unavailable, falling back to SQLite: %s", exc)
        _sb_events = None
WEB_DIR = Path(__file__).resolve().parent / "web"
_default_viz = Path(__file__).resolve().parent / "viz_3d"
VIZ_DIR = Path(os.getenv("VIZ_3D_DIR", str(_default_viz)))
FLOOR_DATA_PATH = WEB_DIR / "maps" / "floor_data.json"


def _age_seconds(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except ValueError:
        return None


def _count(sql: str, params: tuple = ()) -> int:
    return int((db.query_one(sql, params) or {}).get("c", 0))


USAGE_PASSENGER_FILTER = "COALESCE(source, 'INTERACTING') NOT IN ('ESCORT', 'CANCEL')"


def _row_to_robot(row: dict) -> dict:
    return {
        "robot_id": row.get("robot_id"),
        "floor": row.get("floor"),
        "state": row.get("state"),
        "pose": {
            "x": row.get("x"),
            "y": row.get("y"),
            "theta": row.get("theta"),
        },
        "battery": row.get("battery"),
        "current_task_id": row.get("current_task_id"),
        "task_status": row.get("task_status"),
        "error_code": row.get("error_code"),
        "last_seen": row.get("last_seen"),
    }


def _robot_snapshots() -> list[dict]:
    rows = db.query_all("SELECT * FROM latest_robot_status ORDER BY robot_id")
    snapshots = {row["robot_id"]: _row_to_robot(row) for row in rows}
    merged: list[dict] = []
    for robot_id in config.ROBOT_IDS:
        meta = config.ROBOTS.get(robot_id, {})
        snap = snapshots.pop(robot_id, {
            "robot_id": robot_id,
            "state": None,
            "pose": {},
            "battery": None,
            "current_task_id": None,
            "task_status": None,
            "error_code": None,
            "last_seen": None,
        })
        age = _age_seconds(snap.get("last_seen"))
        snap["floor"] = meta.get("floor")
        snap["namespace"] = meta.get("namespace")
        snap["age_s"] = age
        snap["online"] = age is not None and age <= config.STATUS_TIMEOUT
        merged.append(snap)

    for robot_id, snap in sorted(snapshots.items()):
        age = _age_seconds(snap.get("last_seen"))
        snap["floor"] = None
        snap["namespace"] = None
        snap["age_s"] = age
        snap["online"] = age is not None and age <= config.STATUS_TIMEOUT
        merged.append(snap)
    return merged


def create_app(registry, ros_node=None) -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY or os.urandom(24)
    CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})

    pw_hash = generate_password_hash(config.ADMIN_PASSWORD)

    @app.before_request
    def require_login():
        path = request.path
        if path in ("/login", "/logout"):
            return None
        if session.get("user"):
            return None
        if path.startswith("/api/") or path.startswith("/maps/"):
            return jsonify({"error": "auth required"}), 401
        return redirect("/login")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = request.form.get("user", "")
            pw = request.form.get("password", "")
            if user == config.ADMIN_USER and check_password_hash(pw_hash, pw):
                session["user"] = user
                logger.info("login ok: %s", user)
                return redirect("/")
            logger.warning("login failed: %s", user)
            return redirect("/login?e=1")
        return send_from_directory(WEB_DIR, "login.html")

    @app.get("/logout")
    def logout():
        session.pop("user", None)
        return redirect("/login")

    @app.get("/")
    def dashboard():
        return send_from_directory(WEB_DIR, "dashboard.html")

    @app.get("/viz")
    def viz():
        return send_from_directory(VIZ_DIR, "index.html")

    @app.get("/api/maps")
    def maps():
        p = WEB_DIR / "maps" / "maps.json"
        if not p.exists():
            return jsonify({"floors": []})
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

    @app.get("/api/floor_data")
    def floor_data():
        if not FLOOR_DATA_PATH.exists():
            return jsonify({})
        return app.response_class(
            FLOOR_DATA_PATH.read_text(encoding="utf-8"),
            mimetype="application/json",
        )

    @app.post("/api/floor_data")
    def save_floor_data():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "invalid floor data"}), 400
        if not isinstance(data.get("1"), list) or not isinstance(data.get("2"), list):
            return jsonify({"error": "floor data must contain 1 and 2"}), 400
        FLOOR_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        FLOOR_DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return jsonify({"ok": True})

    @app.get("/maps/<path:fname>")
    def map_file(fname: str):
        return send_from_directory(WEB_DIR / "maps", fname)

    @app.get("/api/video_sources")
    def video_sources():
        p = WEB_DIR / "video_sources.json"
        if not p.exists():
            return jsonify({"sources": []})
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "robots": len(_robot_snapshots())})

    @app.get("/api/robots")
    def robots():
        return jsonify(_robot_snapshots())

    @app.get("/api/events")
    def events():
        limit = request.args.get("limit", 50, type=int)
        active = request.args.get("active", type=int)
        if _sb_events:
            return jsonify(_sb_events.list_events(limit=limit, active=bool(active)))
        if active:
            return jsonify(db.query_all(
                "SELECT * FROM events WHERE resolved=0 ORDER BY at DESC LIMIT ?", (limit,)))
        return jsonify(db.query_all(
            "SELECT * FROM events ORDER BY at DESC LIMIT ?", (limit,)))

    @app.post("/api/events/<int:event_id>/resolve")
    def resolve_event(event_id: int):
        user = session.get("user", "operator")
        if _sb_events:
            res = _sb_events.resolve_event(event_id, by=user)
            if not res.get("error"):
                _emit_emergency_resolve_for_event(event_id)
            return jsonify(res), (404 if res.get("error") else 200)
        ev = db.query_one("SELECT id, resolved, robot_id FROM events WHERE id=?", (event_id,))
        if not ev:
            return jsonify({"error": "event not found"}), 404
        if ev["resolved"]:
            return jsonify({"ok": True, "already": True})
        db.execute(
            "UPDATE events SET resolved=1, resolved_at=?, resolved_by=? WHERE id=?",
            (db.utc_now_iso(), user, event_id))
        if ros_node is not None and ev.get("robot_id"):
            ros_node.publish_emergency_resolve(ev["robot_id"])
        return jsonify({"ok": True, "event_id": event_id, "resolved_by": user})

    def _emit_emergency_resolve_for_event(event_id: int) -> None:
        """Supabase 백엔드일 때 resolved 이벤트의 robot_id로 emergency_resolve 발행."""
        if ros_node is None:
            return
        ev = db.query_one("SELECT robot_id FROM events WHERE id=?", (event_id,))
        if ev and ev.get("robot_id"):
            ros_node.publish_emergency_resolve(ev["robot_id"])

    @app.get("/api/robot_log")
    def robot_log():
        limit = request.args.get("limit", 300, type=int)
        robot_id = request.args.get("robot_id")
        if robot_id:
            rows = db.query_all(
                "SELECT robot_id, state, prev_state, task_id, task_status, battery, "
                "x, y, at FROM robot_status_log WHERE robot_id=? "
                "ORDER BY id DESC LIMIT ?", (robot_id, limit))
        else:
            rows = db.query_all(
                "SELECT robot_id, state, prev_state, task_id, task_status, battery, "
                "x, y, at FROM robot_status_log ORDER BY id DESC LIMIT ?", (limit,))
        rows.reverse()
        ids = db.query_all("SELECT DISTINCT robot_id FROM robot_status_log ORDER BY robot_id")
        return jsonify({"robots": [r["robot_id"] for r in ids], "log": rows})

    @app.get("/api/search")
    def search():
        q = (request.args.get("q") or "").strip()
        kind = request.args.get("kind", "all")
        limit = request.args.get("limit", 30, type=int)
        if not q:
            return jsonify({"q": q, "kind": kind, "total": 0, "results": {}})
        like = f"%{q}%"
        out: dict[str, list] = {}
        if kind in ("all", "events"):
            out["events"] = db.query_all(
                "SELECT id, event_type, event_class, robot_id, confidence, floor, at, resolved "
                "FROM events WHERE event_type LIKE ? OR event_class LIKE ? OR robot_id LIKE ? "
                "ORDER BY at DESC LIMIT ?", (like, like, like, limit))
        if kind in ("all", "status"):
            out["status"] = db.query_all(
                "SELECT robot_id, state, prev_state, task_status, battery, at "
                "FROM robot_status_log WHERE robot_id LIKE ? OR state LIKE ? OR task_status LIKE ? "
                "ORDER BY at DESC LIMIT ?", (like, like, like, limit))
        total = sum(len(v) for v in out.values())
        return jsonify({"q": q, "kind": kind, "total": total, "results": out})

    @app.get("/api/stats")
    def stats():
        if _sb_events:
            es = _sb_events.event_stats()
            event_counts = es["by_type"]
            class_counts = es["by_class"]
            ev_total, ev_active = es["total"], es["active"]
        else:
            ev_rows = db.query_all(
                "SELECT event_type, event_class, COUNT(*) c FROM events "
                "GROUP BY event_type, event_class")
            event_counts = {}
            class_counts = {}
            for row in ev_rows:
                event_counts[row["event_type"] or "UNKNOWN"] = (
                    event_counts.get(row["event_type"] or "UNKNOWN", 0) + row["c"])
                if row["event_class"]:
                    class_counts[row["event_class"]] = class_counts.get(row["event_class"], 0) + row["c"]
            ev_total = _count("SELECT COUNT(*) c FROM events")
            ev_active = _count("SELECT COUNT(*) c FROM events WHERE resolved=0")

        languages = {"ko": 0, "zh": 0, "ja": 0, "en": 0, "etc": 0}
        for row in db.query_all(
            "SELECT language, COUNT(*) c FROM ui_usage_log "
            f"WHERE {USAGE_PASSENGER_FILTER} GROUP BY language"
        ):
            code = (row["language"] or "").lower()[:2]
            if code in languages:
                languages[code] += row["c"]
            elif code:
                languages["etc"] += row["c"]

        profiles = {
            row["customer_profile"] or "UNKNOWN": row["c"]
            for row in db.query_all(
                "SELECT customer_profile, COUNT(*) c FROM ui_usage_log "
                f"WHERE {USAGE_PASSENGER_FILTER} GROUP BY customer_profile")
        }
        counters = {
            row["name"]: row["value"]
            for row in db.query_all("SELECT name, value FROM monitor_counters")
        }

        usage_count = _count(f"SELECT COUNT(*) c FROM ui_usage_log WHERE {USAGE_PASSENGER_FILTER}")
        escort_count = _count(
            "SELECT COUNT(*) c FROM ui_usage_log WHERE escort_used=1 OR source='ESCORT'")
        vulnerable = (
            profiles.get("ELDERLY", 0)
            + profiles.get("VISUALLY_IMPAIRED", 0)
            + int(counters.get("vulnerable", 0))
        )

        return jsonify({
            "robots": {
                "known": len(_robot_snapshots()),
                "status_log": _count("SELECT COUNT(*) c FROM robot_status_log"),
            },
            "events": {
                "total": ev_total,
                "active": ev_active,
                "by_type": event_counts,
                "by_class": class_counts,
            },
            "usage": {
                "passengers": usage_count + int(counters.get("passengers", 0)),
                "escorts": escort_count + int(counters.get("escorts", 0)),
                "languages": languages,
                "profiles": profiles,
                "vulnerable": vulnerable,
            },
        })

    # ── 검색 탭 통계: 로봇 / 상태(robot_status_log) / 이벤트 집계 ──────────
    @app.get("/api/search_stats")
    def search_stats():
        # 상태 분포 (robot_status_log) — 검색 'status' 데이터 집계
        status_by_state = {
            (r["state"] or "UNKNOWN"): r["c"]
            for r in db.query_all(
                "SELECT state, COUNT(*) c FROM robot_status_log "
                "GROUP BY state ORDER BY c DESC")
        }
        status_total = _count("SELECT COUNT(*) c FROM robot_status_log")
        log_by_robot = {
            r["robot_id"]: r["c"]
            for r in db.query_all(
                "SELECT robot_id, COUNT(*) c FROM robot_status_log GROUP BY robot_id")
        }
        ev_by_robot = {
            (r["robot_id"] or "UNKNOWN"): r["c"]
            for r in db.query_all(
                "SELECT robot_id, COUNT(*) c FROM events GROUP BY robot_id")
        }

        # 이벤트 type/class/total/active — events 탭과 동일 소스(_sb_events 우선)
        if _sb_events:
            es = _sb_events.event_stats()
            ev_by_type, ev_by_class = es["by_type"], es["by_class"]
            ev_total, ev_active = es["total"], es["active"]
        else:
            ev_by_type = {
                (r["event_type"] or "UNKNOWN"): r["c"]
                for r in db.query_all(
                    "SELECT event_type, COUNT(*) c FROM events GROUP BY event_type")
            }
            ev_by_class = {
                r["event_class"]: r["c"]
                for r in db.query_all(
                    "SELECT event_class, COUNT(*) c FROM events "
                    "WHERE event_class IS NOT NULL GROUP BY event_class")
            }
            ev_total = _count("SELECT COUNT(*) c FROM events")
            ev_active = _count("SELECT COUNT(*) c FROM events WHERE resolved=0")

        # 로봇별 요약 (현재 상태 + 누적 집계)
        robots = []
        for snap in _robot_snapshots():
            rid = snap.get("robot_id")
            robots.append({
                "robot_id": rid,
                "state": snap.get("state"),
                "battery": snap.get("battery"),
                "floor": snap.get("floor"),
                "online": snap.get("online"),
                "log_count": log_by_robot.get(rid, 0),
                "event_count": ev_by_robot.get(rid, 0),
            })

        return jsonify({
            "robots": robots,
            "status": {"total": status_total, "by_state": status_by_state,
                       "by_robot": log_by_robot},
            "events": {"total": ev_total, "active": ev_active,
                       "by_type": ev_by_type, "by_class": ev_by_class,
                       "by_robot": ev_by_robot},
        })

    @app.get("/api/system")
    def system():
        db_ok = True
        try:
            db.query_one("SELECT 1 AS ok")
        except Exception:
            db_ok = False

        snaps = _robot_snapshots()
        online = 0
        for snap in snaps:
            if snap.get("online"):
                online += 1

        counts = {
            "latest_robot_status": _count("SELECT COUNT(*) c FROM latest_robot_status"),
            "robot_status_log": _count("SELECT COUNT(*) c FROM robot_status_log"),
            "events": _count("SELECT COUNT(*) c FROM events"),
            "ui_usage_log": _count("SELECT COUNT(*) c FROM ui_usage_log"),
            "monitor_counters": _count("SELECT COUNT(*) c FROM monitor_counters"),
        }
        return jsonify({
            "ros": {
                "mode": "direct",
                "robot_state_topics": [
                    config.ros_robot_state_topic(robot_id)
                    for robot_id in config.ROBOT_IDS
                ],
                "event_topics": [
                    config.ros_event_topic(robot_id)
                    for robot_id in config.ROBOT_IDS
                ],
                "detection_topics": [
                    config.ros_detection_topic(robot_id)
                    for robot_id in config.ROBOT_IDS
                ],
                "information_topic": config.ROS_INFORMATION_TOPIC,
            },
            "db": {"ok": db_ok, "path": os.path.basename(config.DB_PATH)},
            "robots": {
                "total": len(snaps),
                "online": online,
                "offline": len(snaps) - online,
                "timeout_s": config.STATUS_TIMEOUT,
            },
            "counts": counts,
        })

    @app.get("/api/control_stats")
    def control_stats():
        stats_data = stats().get_json()
        return jsonify(stats_data["usage"] | {"events": stats_data["events"]["by_type"]})

    return app


def run_api(registry, ros_node=None, host: str | None = None, port: int | None = None) -> None:
    app = create_app(registry, ros_node)
    host = host or config.FLASK_HOST
    port = port or config.FLASK_PORT
    logger.info("Flask API on http://%s:%s", host, port)
    app.run(host=host, port=port, threaded=True, use_reloader=False, debug=False)
