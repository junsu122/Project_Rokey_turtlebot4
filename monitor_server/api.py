"""Read-only Flask API for the monitoring dashboard."""

from __future__ import annotations

import logging
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db


logger = logging.getLogger("monitor.api")
WEB_DIR = Path(__file__).resolve().parent / "web"
VIZ_DIR = Path(__file__).resolve().parent.parent / "viz_3d"


def _age_seconds(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except ValueError:
        return None


def _count(sql: str, params: tuple = ()) -> int:
    return int((db.query_one(sql, params) or {}).get("c", 0))


def _robot_snapshots(registry) -> list[dict]:
    snapshots = {snap["robot_id"]: dict(snap) for snap in registry.all_snapshots()}
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


def create_app(registry) -> Flask:
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
        return jsonify({"status": "ok", "robots": len(_robot_snapshots(registry))})

    @app.get("/api/robots")
    def robots():
        return jsonify(_robot_snapshots(registry))

    @app.get("/api/events")
    def events():
        limit = request.args.get("limit", 50, type=int)
        active = request.args.get("active", type=int)
        if active:
            return jsonify(db.query_all(
                "SELECT * FROM events WHERE resolved=0 ORDER BY at DESC LIMIT ?", (limit,)))
        return jsonify(db.query_all(
            "SELECT * FROM events ORDER BY at DESC LIMIT ?", (limit,)))

    @app.post("/api/events/<int:event_id>/resolve")
    def resolve_event(event_id: int):
        ev = db.query_one("SELECT id, resolved FROM events WHERE id=?", (event_id,))
        if not ev:
            return jsonify({"error": "event not found"}), 404
        if ev["resolved"]:
            return jsonify({"ok": True, "already": True})
        user = session.get("user", "operator")
        db.execute(
            "UPDATE events SET resolved=1, resolved_at=?, resolved_by=? WHERE id=?",
            (db.utc_now_iso(), user, event_id))
        return jsonify({"ok": True, "event_id": event_id, "resolved_by": user})

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
        ev_rows = db.query_all(
            "SELECT event_type, event_class, COUNT(*) c FROM events "
            "GROUP BY event_type, event_class")
        event_counts: dict[str, int] = {}
        class_counts: dict[str, int] = {}
        for row in ev_rows:
            event_counts[row["event_type"] or "UNKNOWN"] = (
                event_counts.get(row["event_type"] or "UNKNOWN", 0) + row["c"])
            if row["event_class"]:
                class_counts[row["event_class"]] = class_counts.get(row["event_class"], 0) + row["c"]

        languages = {"ko": 0, "zh": 0, "ja": 0, "en": 0, "etc": 0}
        for row in db.query_all("SELECT language, COUNT(*) c FROM ui_usage_log GROUP BY language"):
            code = (row["language"] or "").lower()[:2]
            if code in languages:
                languages[code] += row["c"]
            elif code:
                languages["etc"] += row["c"]

        profiles = {
            row["customer_profile"] or "UNKNOWN": row["c"]
            for row in db.query_all(
                "SELECT customer_profile, COUNT(*) c FROM ui_usage_log GROUP BY customer_profile")
        }
        counters = {
            row["name"]: row["value"]
            for row in db.query_all("SELECT name, value FROM monitor_counters")
        }

        usage_count = _count("SELECT COUNT(*) c FROM ui_usage_log")
        escort_count = _count("SELECT COUNT(*) c FROM ui_usage_log WHERE escort_used=1")
        vulnerable = (
            profiles.get("ELDERLY", 0)
            + profiles.get("VISUALLY_IMPAIRED", 0)
            + int(counters.get("vulnerable", 0))
        )

        return jsonify({
            "robots": {
                "known": len(_robot_snapshots(registry)),
                "status_log": _count("SELECT COUNT(*) c FROM robot_status_log"),
            },
            "events": {
                "total": _count("SELECT COUNT(*) c FROM events"),
                "active": _count("SELECT COUNT(*) c FROM events WHERE resolved=0"),
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

    @app.get("/api/system")
    def system():
        mqtt_ok = False
        try:
            with socket.create_connection((config.MQTT_HOST, config.MQTT_PORT), timeout=0.4):
                mqtt_ok = True
        except OSError:
            mqtt_ok = False

        db_ok = True
        try:
            db.query_one("SELECT 1 AS ok")
        except Exception:
            db_ok = False

        snaps = _robot_snapshots(registry)
        online = 0
        for snap in snaps:
            if snap.get("online"):
                online += 1

        counts = {
            "robot_status_log": _count("SELECT COUNT(*) c FROM robot_status_log"),
            "events": _count("SELECT COUNT(*) c FROM events"),
            "ui_usage_log": _count("SELECT COUNT(*) c FROM ui_usage_log"),
            "monitor_counters": _count("SELECT COUNT(*) c FROM monitor_counters"),
        }
        return jsonify({
            "mqtt": {"ok": mqtt_ok, "host": config.MQTT_HOST, "port": config.MQTT_PORT},
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


def run_api(registry, host: str | None = None, port: int | None = None) -> None:
    app = create_app(registry)
    host = host or config.FLASK_HOST
    port = port or config.FLASK_PORT
    logger.info("Flask API on http://%s:%s", host, port)
    app.run(host=host, port=port, threaded=True, use_reloader=False, debug=False)
