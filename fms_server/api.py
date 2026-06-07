"""Flask 조회 API — **읽기 전용 GET만** (절대 규칙 7).

별도 스레드에서 구동. 로봇 제어·미션 생성을 HTTP로 받지 않는다(그건 MQTT IF-01).
M1: /api/robots(메모리 스냅샷), /api/health. /missions·/events는 M2+에서 추가.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db


logger = logging.getLogger("fms.api")
WEB_DIR = Path(__file__).resolve().parent / "web"


def create_app(registry) -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY or os.urandom(24)
    CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})

    # 비밀번호 해시는 기동 시 1회 계산(평문 비교 회피)
    pw_hash = generate_password_hash(config.ADMIN_PASSWORD)

    # ── 로그인 가드 (평가지표: system monitor 로그인) ────────────────────
    # /login·/logout만 공개, 그 외는 세션 필요. 미인증 시 API는 401, 페이지는 /login.
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

    # 관제 대시보드(읽기 전용 정적 페이지). 브라우저가 /api/* 를 폴링한다.
    @app.get("/")
    def dashboard():
        return send_from_directory(WEB_DIR, "dashboard.html")

    # 맵 메타(층·로봇·해상도·원점·픽셀크기) + 맵 이미지(png) 서빙
    @app.get("/api/maps")
    def maps():
        p = WEB_DIR / "maps" / "maps.json"
        if not p.exists():
            return jsonify({"floors": []})
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

    @app.get("/maps/<path:fname>")
    def map_file(fname: str):
        return send_from_directory(WEB_DIR / "maps", fname)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "robots": len(registry.all_snapshots())})

    @app.get("/api/robots")
    def robots():
        # 로봇별 최신 IF-02 스냅샷 (메모리). DB 조회 아님 — 실시간성 우선.
        return jsonify(registry.all_snapshots())

    @app.get("/api/missions")
    def missions():
        limit = request.args.get("limit", 20, type=int)
        rows = db.query_all(
            "SELECT * FROM missions ORDER BY created_at DESC LIMIT ?", (limit,))
        active = [r for r in rows if r["state"] not in
                  ("COMPLETED", "CANCELLED", "EMERGENCY", "FAILED")]
        return jsonify({"missions": rows, "active": active})

    @app.get("/api/missions/<mission_id>")
    def mission_detail(mission_id: str):
        m = db.query_one("SELECT * FROM missions WHERE mission_id=?", (mission_id,))
        if not m:
            return jsonify({"error": "mission not found"}), 404
        m["transitions"] = db.query_all(
            "SELECT from_state, to_state, trigger, at FROM mission_transitions "
            "WHERE mission_id=? ORDER BY id", (mission_id,))
        m["tasks"] = db.query_all(
            "SELECT task_id, robot_id, task_type, goal_poi, issued_at, ack, "
            "final_status, finished_at FROM tasks WHERE mission_id=? ORDER BY issued_at",
            (mission_id,))
        return jsonify(m)

    @app.get("/api/events")
    def events():
        limit = request.args.get("limit", 50, type=int)
        return jsonify(db.query_all(
            "SELECT * FROM events ORDER BY at DESC LIMIT ?", (limit,)))

    @app.get("/api/search")
    def search():
        # 저장된 기록 검색 (평가지표: DB 활용 — 저장 내용 검색). GET 조회만.
        q = (request.args.get("q") or "").strip()
        kind = request.args.get("kind", "all")
        limit = request.args.get("limit", 20, type=int)
        if not q:
            return jsonify({"q": q, "kind": kind, "results": {}})
        like = f"%{q}%"
        out: dict[str, list] = {}
        if kind in ("all", "missions"):
            out["missions"] = db.query_all(
                "SELECT mission_id, state, start_robot, next_robot, dest_poi, "
                "handover_latency_ms, created_at FROM missions "
                "WHERE mission_id LIKE ? OR state LIKE ? OR dest_poi LIKE ? "
                "OR start_robot LIKE ? OR next_robot LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (like, like, like, like, like, limit))
        if kind in ("all", "events"):
            out["events"] = db.query_all(
                "SELECT event_type, robot_id, confidence, floor, at FROM events "
                "WHERE event_type LIKE ? OR robot_id LIKE ? "
                "ORDER BY at DESC LIMIT ?", (like, like, limit))
        if kind in ("all", "tasks"):
            out["tasks"] = db.query_all(
                "SELECT task_id, mission_id, robot_id, task_type, ack, final_status, "
                "issued_at FROM tasks "
                "WHERE task_id LIKE ? OR task_type LIKE ? OR robot_id LIKE ? OR mission_id LIKE ? "
                "ORDER BY issued_at DESC LIMIT ?", (like, like, like, like, limit))
        total = sum(len(v) for v in out.values())
        return jsonify({"q": q, "kind": kind, "total": total, "results": out})

    @app.get("/api/stats")
    def stats():
        # 기록(DB)으로부터 수락 기준 지표를 산출 — 라이브 경로 아님(절대 규칙 6 유지).
        rows = db.query_all("SELECT state, handover_latency_ms FROM missions")
        total = len(rows)
        by_state: dict[str, int] = {}
        for r in rows:
            by_state[r["state"]] = by_state.get(r["state"], 0) + 1

        terminal = ("COMPLETED", "CANCELLED", "EMERGENCY", "FAILED")
        completed = by_state.get("COMPLETED", 0)
        finished = sum(by_state.get(s, 0) for s in terminal)

        target = config.HANDOVER_TARGET_MS
        lat = sorted(r["handover_latency_ms"] for r in rows
                     if r["handover_latency_ms"] is not None)

        def pct(p: float):
            if not lat:
                return None
            k = (len(lat) - 1) * p
            f = int(k)
            c = min(f + 1, len(lat) - 1)
            return round(lat[f] + (lat[c] - lat[f]) * (k - f))

        passed = sum(1 for v in lat if v <= target)
        handover = {
            "measured": len(lat),                # 핸드오버가 있었던(릴레이) 미션 수
            "target_ms": target,
            "avg_ms": round(sum(lat) / len(lat)) if lat else None,
            "min_ms": lat[0] if lat else None,
            "max_ms": lat[-1] if lat else None,
            "p95_ms": pct(0.95),
            "pass": passed,
            "pass_rate": round(passed / len(lat), 4) if lat else None,
        }

        ev = db.query_all("SELECT event_type, COUNT(*) c FROM events GROUP BY event_type")
        events_stat = {
            "total": sum(e["c"] for e in ev),
            "by_type": {e["event_type"]: e["c"] for e in ev},
        }

        return jsonify({
            "missions": {
                "total": total,
                "by_state": by_state,
                "completed": completed,
                "finished": finished,
                "same_floor": sum(1 for r in rows
                                  if r["state"] == "COMPLETED" and r["handover_latency_ms"] is None),
                "success_rate": round(completed / finished, 4) if finished else None,
            },
            "handover": handover,
            "events": events_stat,
        })

    return app


def run_api(registry, host: str | None = None, port: int | None = None) -> None:
    app = create_app(registry)
    host = host or config.FLASK_HOST
    port = port or config.FLASK_PORT
    logger.info("Flask API on http://%s:%s (read-only GET)", host, port)
    # 데모 LAN 전제: 개발 서버로 충분. 리로더 끔(스레드 구동).
    app.run(host=host, port=port, threaded=True, use_reloader=False, debug=False)
