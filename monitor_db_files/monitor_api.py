#!/usr/bin/env python3
"""읽기 API + UI 서빙 — 독립 모니터링 스택의 "읽는 쪽".

db_bridge / ros_db_bridge 가 monitor.db 에 적재한 데이터를, 기존 UI(대시보드/viz_3d)가
기대하는 `/api/*` 형태로 매핑해 내려준다. FMS(:5000)와 충돌 않도록 **기본 포트 5001**.

서빙:
  /            → 일반 UI (대시보드, 탭)           fms_server/web/dashboard.html 재사용
  /viz         → 3D 뷰                            viz_3d/index.html
  /api/robots /missions /events /stats /system /control_stats /robot_log
  /api/transitions /requests /search /maps /video_sources
  POST /api/events/<id>/resolve   (조치 완료)

실행:  python3 monitor_api.py            # http://localhost:5001/
"""
from __future__ import annotations

import hashlib
import logging
import os
import socket
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory

import monitor_db as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monitor_api")

ROOT = Path(__file__).resolve().parents[1]
VIZ_DIR = ROOT / "viz_3d"
FMS_WEB = ROOT / "fms_server" / "web"        # 대시보드·맵·video_sources 재사용
API_HOST = os.getenv("MONITOR_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("MONITOR_API_PORT", "5001"))
MQTT_HOST = os.getenv("MONITOR_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MONITOR_MQTT_PORT", "1883"))

# monitor 이벤트 타입 → UI 비콘/배지 종류
EVENT_VIZ_MAP = {
    db.EVENT_FIRE_DETECTED: "FIRE",
    db.EVENT_THREAT_DETECTED: "SUSPICIOUS_PERSON",
    db.EVENT_EMERGENCY_PATIENT: "EMERGENCY_PATIENT",
    db.EVENT_EMERGENCY_ACTION: "SUSPICIOUS_PERSON",
}
TERMINAL = ("COMPLETED", "CANCELLED", "EMERGENCY", "FAILED")
_ID_MAP: dict[int, str] = {}   # 숫자 id(UI) → event_id(uuid) 역매핑 (resolve용)


def _num_id(event_id: str) -> int:
    return int(hashlib.sha1(str(event_id).encode()).hexdigest()[:8], 16)


def _mission_view(m: dict) -> dict:
    return {
        "mission_id": m.get("mission_id"),
        "state": m.get("state"),
        "start_robot": m.get("start_robot_id"),
        "next_robot": m.get("next_robot_id"),
        "dest_poi": m.get("destination_id"),
        "handover_latency_ms": None,
        "created_at": m.get("created_at"),
        "language": m.get("customer_language"),
    }


def create_app() -> Flask:
    app = Flask(__name__)
    db.init_db()
    db.seed_default_robots()
    try:
        db.get_conn().execute("PRAGMA journal_mode=WAL;")
        cols = {r["name"] for r in db.get_conn().execute("PRAGMA table_info(monitor_events)")}
        if "resolved" not in cols:
            db.get_conn().execute("ALTER TABLE monitor_events ADD COLUMN resolved INTEGER DEFAULT 0")
        db.get_conn().commit()
    except Exception as e:
        logger.warning("startup pragma/migrate: %s", e)

    # ── UI 서빙 ────────────────────────────────────────────────────────
    @app.get("/")
    def index():
        return send_from_directory(FMS_WEB, "dashboard.html")

    @app.get("/viz")
    def viz():
        return send_from_directory(VIZ_DIR, "index.html")

    @app.get("/logout")
    def logout():
        return redirect("/")            # monitor 스택은 인증 없음 — 깨짐 방지용

    @app.get("/maps/<path:fname>")
    def map_file(fname: str):
        return send_from_directory(FMS_WEB / "maps", fname)

    @app.get("/api/maps")
    def maps():
        p = FMS_WEB / "maps" / "maps.json"
        if not p.exists():
            return jsonify({"floors": []})
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

    @app.get("/api/video_sources")
    def video_sources():
        p = FMS_WEB / "video_sources.json"
        if not p.exists():
            return jsonify({"sources": []})
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "db": os.path.basename(str(db.DB_PATH))})

    # ── 실시간 ─────────────────────────────────────────────────────────
    @app.get("/api/robots")
    def robots():
        out = []
        for r in db.list_latest_robots():
            if r.get("x") is None or r.get("y") is None:
                continue
            out.append({
                "robot_id": r["robot_id"], "state": r.get("state"),
                "battery": r.get("battery"), "current_task_id": r.get("current_task_id"),
                "task_status": r.get("task_status"), "last_seen": r.get("last_seen"),
                "pose": {"x": r.get("x"), "y": r.get("y"), "theta": r.get("theta")},
            })
        return jsonify(out)

    @app.get("/api/missions")
    def missions():
        rows = [_mission_view(m) for m in db.query_all(
            "SELECT * FROM missions ORDER BY created_at DESC LIMIT 20")]
        active = [m for m in rows if m["state"] not in TERMINAL]
        return jsonify({"missions": rows, "active": active})

    @app.get("/api/missions/<mission_id>")
    def mission_detail(mission_id: str):
        m = db.query_one("SELECT * FROM missions WHERE mission_id=?", (mission_id,))
        if not m:
            return jsonify({"error": "not found"}), 404
        v = _mission_view(m)
        rows = db.query_all(
            "SELECT state, event_type, at FROM mission_state_log "
            "WHERE mission_id=? ORDER BY id", (mission_id,))
        prev = None
        trs = []
        for r in rows:
            trs.append({"from_state": prev, "to_state": r["state"],
                        "trigger": r["event_type"], "at": r["at"]})
            prev = r["state"]
        v["transitions"] = trs
        v["tasks"] = []
        return jsonify(v)

    @app.get("/api/events")
    def events():
        limit = request.args.get("limit", 100, type=int)
        active = request.args.get("active", type=int)
        out = []
        for e in db.list_recent_events(limit):
            vt = EVENT_VIZ_MAP.get(e.get("event_type"))
            if not vt:
                continue
            if e.get("x") is None or e.get("y") is None or e.get("floor") is None:
                continue
            resolved = int(e.get("resolved") or 0)
            if active and resolved:
                continue
            nid = _num_id(e["event_id"])
            _ID_MAP[nid] = e["event_id"]
            out.append({
                "id": nid, "event_type": vt, "robot_id": e.get("robot_id"),
                "confidence": e.get("confidence"), "x": e.get("x"), "y": e.get("y"),
                "floor": e.get("floor"), "at": e.get("at"),
                "resolved": resolved, "resolved_by": e.get("resolved_by"),
            })
        return jsonify(out)

    @app.post("/api/events/<int:event_id>/resolve")
    def resolve_event(event_id: int):
        eid = _ID_MAP.get(event_id)
        if not eid:
            return jsonify({"error": "unknown event"}), 404
        db.execute("UPDATE monitor_events SET resolved=1 WHERE event_id=?", (eid,))
        return jsonify({"ok": True, "event_id": event_id})

    # ── 분석/관제 ──────────────────────────────────────────────────────
    @app.get("/api/stats")
    def stats():
        rows = db.query_all("SELECT state FROM missions")
        by_state: dict[str, int] = {}
        for r in rows:
            by_state[r["state"]] = by_state.get(r["state"], 0) + 1
        completed = by_state.get("COMPLETED", 0)
        finished = sum(by_state.get(s, 0) for s in TERMINAL)
        s = db.monitor_stats()
        ev_total = s["fire_count"] + s["emergency_patient_count"] + s["threat"]["total_count"]
        return jsonify({
            "missions": {"total": len(rows), "by_state": by_state, "completed": completed,
                         "finished": finished, "same_floor": 0,
                         "success_rate": round(completed / finished, 4) if finished else None},
            "handover": {"measured": 0, "target_ms": 3000, "avg_ms": None, "min_ms": None,
                         "max_ms": None, "p95_ms": None, "pass": 0, "pass_rate": None},
            "events": {"total": ev_total, "by_type": {
                "FIRE": s["fire_count"], "EMERGENCY_PATIENT": s["emergency_patient_count"],
                "THREAT": s["threat"]["total_count"]}},
        })

    @app.get("/api/control_stats")
    def control_stats():
        s = db.monitor_stats()
        languages = dict(s["language_counts"]); languages["etc"] = 0
        return jsonify({
            "passengers": s["user_count"],
            "escorts": s["escort"]["completed_count"],
            "languages": languages,
            "profile": ({"TRANSPORTATION_WEAK": s["transportation_weak_count"]}
                        if s["transportation_weak_count"] else {}),
            "vulnerable": s["transportation_weak_count"],
            "events": {"fire": s["fire_count"], "suspicious": s["threat"]["total_count"],
                       "patient": s["emergency_patient_count"]},
        })

    @app.get("/api/system")
    def system():
        mqtt_ok = False
        try:
            with socket.create_connection((MQTT_HOST, MQTT_PORT), timeout=0.4):
                mqtt_ok = True
        except OSError:
            pass
        snaps = db.list_latest_robots()
        online = sum(1 for r in snaps if r.get("online"))
        one = lambda t: (db.query_one(f"SELECT COUNT(*) c FROM {t}") or {}).get("c", 0)  # noqa
        return jsonify({
            "mqtt": {"ok": mqtt_ok, "host": MQTT_HOST, "port": MQTT_PORT},
            "db": {"ok": True, "path": os.path.basename(str(db.DB_PATH))},
            "robots": {"total": len(snaps), "online": online,
                       "offline": len(snaps) - online, "timeout_s": 10},
            "counts": {"missions": one("missions"), "requests": 0,
                       "tasks": 0, "status_log": one("robot_status_log"),
                       "events": one("monitor_events")},
        })

    @app.get("/api/robot_log")
    def robot_log():
        limit = request.args.get("limit", 300, type=int)
        rid = request.args.get("robot_id")
        if rid:
            rows = db.query_all("SELECT robot_id, state, battery, x, y, at FROM robot_status_log "
                                "WHERE robot_id=? ORDER BY id DESC LIMIT ?", (rid, limit))
        else:
            rows = db.query_all("SELECT robot_id, state, battery, x, y, at FROM robot_status_log "
                                "ORDER BY id DESC LIMIT ?", (limit,))
        rows.reverse()
        ids = db.query_all("SELECT DISTINCT robot_id FROM robot_status_log ORDER BY robot_id")
        return jsonify({"robots": [r["robot_id"] for r in ids], "log": rows})

    @app.get("/api/transitions")
    def transitions():
        limit = request.args.get("limit", 12, type=int)
        mids = db.query_all("SELECT mission_id, MAX(id) mx FROM mission_state_log "
                            "GROUP BY mission_id ORDER BY mx DESC LIMIT ?", (limit,))
        out = []
        for row in mids:
            mid = row["mission_id"]
            m = db.query_one("SELECT * FROM missions WHERE mission_id=?", (mid,))
            rows = db.query_all("SELECT state, event_type, at FROM mission_state_log "
                                "WHERE mission_id=? ORDER BY id", (mid,))
            prev = None; trs = []
            for r in rows:
                trs.append({"from_state": prev, "to_state": r["state"],
                            "trigger": r["event_type"], "at": r["at"]})
                prev = r["state"]
            out.append({"mission": _mission_view(m) if m else None, "transitions": trs})
        return jsonify({"missions": out})

    @app.get("/api/requests")
    def requests_list():
        return jsonify({"requests": [], "tasks": []})   # monitor 스키마엔 별도 requests 없음

    @app.get("/api/search")
    def search():
        q = (request.args.get("q") or "").strip()
        kind = request.args.get("kind", "all")
        if not q:
            return jsonify({"q": q, "kind": kind, "results": {}})
        like = f"%{q}%"
        out: dict[str, list] = {}
        if kind in ("all", "missions"):
            out["missions"] = [_mission_view(m) for m in db.query_all(
                "SELECT * FROM missions WHERE mission_id LIKE ? OR state LIKE ? "
                "OR destination_id LIKE ? ORDER BY created_at DESC LIMIT 20",
                (like, like, like))]
        if kind in ("all", "events"):
            out["events"] = db.query_all(
                "SELECT event_type, robot_id, confidence, floor, at FROM monitor_events "
                "WHERE event_type LIKE ? OR robot_id LIKE ? ORDER BY at DESC LIMIT 20",
                (like, like))
        total = sum(len(v) for v in out.values())
        return jsonify({"q": q, "kind": kind, "total": total, "results": out})

    return app


if __name__ == "__main__":
    app = create_app()
    logger.info("monitor_api on http://%s:%s/  (DB: %s)", API_HOST, API_PORT, db.DB_PATH)
    app.run(host=API_HOST, port=API_PORT, threaded=True, use_reloader=False)
