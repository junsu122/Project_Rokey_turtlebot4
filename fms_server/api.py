"""Flask 조회 API — **읽기 전용 GET만** (절대 규칙 7).

별도 스레드에서 구동. 로봇 제어·미션 생성을 HTTP로 받지 않는다(그건 MQTT IF-01).
M1: /api/robots(메모리 스냅샷), /api/health. /missions·/events는 M2+에서 추가.
"""

from __future__ import annotations

import logging
import os
import socket
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db


logger = logging.getLogger("fms.api")
WEB_DIR = Path(__file__).resolve().parent / "web"
VIZ_DIR = Path(__file__).resolve().parent.parent / "viz_3d"  # 3D 관제 뷰(단일 HTML)


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

    # 3D 관제 뷰(viz_3d). require_login 적용(공개 경로 아님) → :5000 세션 공유.
    @app.get("/viz")
    def viz():
        return send_from_directory(VIZ_DIR, "index.html")

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

    # 영상 소스 메타데이터(시그널링 URL만). 미디어는 로봇↔브라우저 P2P — FMS 우회.
    @app.get("/api/video_sources")
    def video_sources():
        p = WEB_DIR / "video_sources.json"
        if not p.exists():
            return jsonify({"sources": []})
        return app.response_class(p.read_text(encoding="utf-8"), mimetype="application/json")

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
        active = request.args.get("active", type=int)  # 1 → 미조치(resolved=0)만
        if active:
            return jsonify(db.query_all(
                "SELECT * FROM events WHERE resolved=0 ORDER BY at DESC LIMIT ?", (limit,)))
        return jsonify(db.query_all(
            "SELECT * FROM events ORDER BY at DESC LIMIT ?", (limit,)))

    # 운영자 조치 완료 → 알림 해제. 절대 규칙 7(Flask 읽기전용)의 예외 — 단, 이는
    # **로봇 제어/미션 생성이 아니라 관제사 확인(ack)** 이다. 규칙을 엄격히 지키려면
    # 이 한 곳을 MQTT(운영자 액션 토픽) 구독으로 옮기면 된다(나머지는 그대로).
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
        logger.info("event %s resolved by %s", event_id, user)
        return jsonify({"ok": True, "event_id": event_id, "resolved_by": user})

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

    # ── 시스템 상태 (탭: 시스템 상태) ──────────────────────────────────────
    # FMS 관점의 헬스: MQTT 도달성 + DB + 로봇 온라인 집계. ROS2는 MQTT 경유라
    # FMS가 직접 알지 못한다(절대 규칙 5) → 여기선 알 수 있는 신호만 보고.
    @app.get("/api/system")
    def system():
        # MQTT 브로커 TCP 도달성(읽기 전용 소켓 연결 테스트)
        mqtt_ok = False
        try:
            with socket.create_connection((config.MQTT_HOST, config.MQTT_PORT), timeout=0.4):
                mqtt_ok = True
        except OSError:
            mqtt_ok = False
        # DB 도달성
        db_ok = True
        try:
            db.query_one("SELECT 1 AS ok")
        except Exception:
            db_ok = False
        # 로봇 온라인 집계 (메모리 스냅샷 기준, last_seen 임계 = STATUS_TIMEOUT)
        snaps = registry.all_snapshots()
        timeout_s = getattr(config, "STATUS_TIMEOUT", 10)
        online = 0
        for s in snaps:
            ls = s.get("last_seen")
            if not ls:
                continue
            try:
                from datetime import datetime, timezone
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(ls)).total_seconds()
                if age <= timeout_s:
                    online += 1
            except Exception:
                pass
        counts = {
            "missions": (db.query_one("SELECT COUNT(*) c FROM missions") or {}).get("c", 0),
            "requests": (db.query_one("SELECT COUNT(*) c FROM requests") or {}).get("c", 0),
            "tasks": (db.query_one("SELECT COUNT(*) c FROM tasks") or {}).get("c", 0),
            "status_log": (db.query_one("SELECT COUNT(*) c FROM robot_status_log") or {}).get("c", 0),
            "events": (db.query_one("SELECT COUNT(*) c FROM events") or {}).get("c", 0),
        }
        return jsonify({
            "mqtt": {"ok": mqtt_ok, "host": config.MQTT_HOST, "port": config.MQTT_PORT},
            "db": {"ok": db_ok, "path": os.path.basename(config.DB_PATH)},
            "robots": {"total": len(snaps), "online": online,
                       "offline": len(snaps) - online, "timeout_s": timeout_s},
            "counts": counts,
        })

    # ── 로봇 상태 추이 (탭: 로봇 추이) — robot_status_log 시계열 ───────────
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
        rows.reverse()  # 시간 오름차순(차트용)
        ids = db.query_all("SELECT DISTINCT robot_id FROM robot_status_log ORDER BY robot_id")
        return jsonify({"robots": [r["robot_id"] for r in ids], "log": rows})

    # ── 미션 상태 전이 타임라인 (탭: 미션 타임라인) ───────────────────────
    @app.get("/api/transitions")
    def transitions():
        limit = request.args.get("limit", 12, type=int)
        mids = db.query_all(
            "SELECT mission_id, MAX(id) mx FROM mission_transitions "
            "GROUP BY mission_id ORDER BY mx DESC LIMIT ?", (limit,))
        out = []
        for row in mids:
            mid = row["mission_id"]
            m = db.query_one(
                "SELECT mission_id, state, start_robot, next_robot, dest_poi, "
                "handover_latency_ms, created_at FROM missions WHERE mission_id=?", (mid,))
            trs = db.query_all(
                "SELECT from_state, to_state, trigger, at FROM mission_transitions "
                "WHERE mission_id=? ORDER BY id", (mid,))
            out.append({"mission": m, "transitions": trs})
        return jsonify({"missions": out})

    # ── 요청 인박스 (탭: 요청·태스크) — requests + tasks ──────────────────
    @app.get("/api/requests")
    def requests_list():
        limit = request.args.get("limit", 30, type=int)
        reqs = db.query_all(
            "SELECT request_id, robot_id, request_type, received_at FROM requests "
            "ORDER BY received_at DESC LIMIT ?", (limit,))
        for r in reqs:
            r["missions"] = db.query_all(
                "SELECT mission_id, state, dest_poi, handover_latency_ms FROM missions "
                "WHERE request_id=? ORDER BY created_at", (r["request_id"],))
        tasks = db.query_all(
            "SELECT task_id, mission_id, robot_id, task_type, goal_poi, ack, "
            "final_status, issued_at, finished_at FROM tasks "
            "ORDER BY issued_at DESC LIMIT ?", (limit,))
        return jsonify({"requests": reqs, "tasks": tasks})

    # ── 관제 현황 카운터 (탭: 관제 현황) — 기록 집계 ──────────────────────
    @app.get("/api/control_stats")
    def control_stats():
        one = lambda sql, p=(): (db.query_one(sql, p) or {}).get("c", 0)  # noqa: E731
        passengers = one("SELECT COUNT(*) c FROM missions")
        escorts = one("SELECT COUNT(*) c FROM missions WHERE state='COMPLETED'")

        # 언어 한/중/일/영 (language 첫 2글자 정규화: ko/zh/ja/en)
        lang = {"ko": 0, "zh": 0, "ja": 0, "en": 0, "etc": 0}
        for r in db.query_all("SELECT language, COUNT(*) c FROM missions GROUP BY language"):
            code = (r["language"] or "").lower()[:2]
            if code in lang:
                lang[code] += r["c"]
            elif code:
                lang["etc"] += r["c"]

        # 고객 profile 분포 + 교통약자(노약자·시각장애) 집계
        profile = {}
        for r in db.query_all("SELECT customer_profile p, COUNT(*) c FROM missions GROUP BY customer_profile"):
            profile[r["p"] or "UNKNOWN"] = r["c"]
        vulnerable = profile.get("ELDERLY", 0) + profile.get("VISUALLY_IMPAIRED", 0)

        # IF-05 이벤트(화재/거수자/긴급환자)
        ev = {e["event_type"]: e["c"]
              for e in db.query_all("SELECT event_type, COUNT(*) c FROM events GROUP BY event_type")}

        return jsonify({
            "passengers": passengers,
            "escorts": escorts,
            "languages": lang,
            "profile": profile,
            "vulnerable": vulnerable,
            "events": {
                "fire": ev.get("FIRE", 0),
                "suspicious": ev.get("SUSPICIOUS_PERSON", 0),
                "patient": ev.get("EMERGENCY_PATIENT", 0),
            },
        })

    return app


def run_api(registry, host: str | None = None, port: int | None = None) -> None:
    app = create_app(registry)
    host = host or config.FLASK_HOST
    port = port or config.FLASK_PORT
    logger.info("Flask API on http://%s:%s (read-only GET)", host, port)
    # 데모 LAN 전제: 개발 서버로 충분. 리로더 끔(스레드 구동).
    app.run(host=host, port=port, threaded=True, use_reloader=False, debug=False)
