"""통합 테스트 — 실행 중인 MQTT 브로커(Mosquitto/amqtt) 대상 M1·M2·M3 전체 검증.

전제: 브로커가 localhost:1883에 떠 있어야 한다.
    sudo systemctl start mosquitto      # 또는: mosquitto -d / amqtt

실행:
    python3 tools/integration_test.py
    FMS_MQTT_HOST=192.168.0.10 python3 tools/integration_test.py   # 원격 브로커

검증 항목:
    [정상] 1) IF-02 파이프라인  2) 층간 릴레이(+3초 측정)  3) 같은 층 직행
    [예외] 4) CANCEL  5) EMERGENCY  6) task FAILED  7) status timeout
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.STATUS_TIMEOUT = 3.0  # 테스트 단축(기본 10s) — timeout 시나리오 빠르게

import api  # noqa: E402
import db  # noqa: E402
import event_service  # noqa: E402
import messages  # noqa: E402
from mission_manager import MissionManager  # noqa: E402
from robot_registry import RobotRegistry  # noqa: E402
from transport import MqttTransport  # noqa: E402
from mock_robot import MockRobot  # noqa: E402

API_PORT = 5059


HOST = os.getenv("FMS_MQTT_HOST", "localhost")
PORT = int(os.getenv("FMS_MQTT_PORT", "1883"))
DB_PATH = "/tmp/fms_integration.db"


def main() -> int:
    for f in (DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm"):
        if os.path.exists(f):
            os.remove(f)
    db.init_db(DB_PATH)

    reg = RobotRegistry()
    fms = MqttTransport(client_id="fms_server")
    mm = MissionManager(fms, reg)
    try:
        fms.connect()
    except (ConnectionRefusedError, OSError) as err:
        print(f"❌ 브로커 연결 실패 ({HOST}:{PORT}): {err}")
        print("   → Mosquitto 기동 후 다시 실행: sudo systemctl start mosquitto")
        return 2
    fms.loop_start()
    fms.subscribe(config.TOPIC_STATUS_WILDCARD,
                  lambda t, p: (reg.update_from_status(p), mm.on_robot_status(p)),
                  config.QOS_STATUS)
    fms.subscribe(config.TOPIC_REQUEST_WILDCARD, lambda t, p: mm.on_request(p), config.QOS_REQUEST)
    fms.subscribe(config.TOPIC_TASK_ACK_WILDCARD, lambda t, p: mm.on_task_ack(p), config.QOS_TASK_ACK)
    fms.subscribe(config.TOPIC_EVENT_WILDCARD, lambda t, p: event_service.record_event(p), config.QOS_EVENT)

    # 타임아웃 감시 스레드 (main.py의 _watch_status_timeout과 동일 패턴)
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            mm.check_timeouts()
            stop.wait(0.4)

    threading.Thread(target=watch, daemon=True).start()

    # 관제 조회 API 스레드 (읽기 전용)
    threading.Thread(target=api.run_api, args=(reg,), kwargs={"port": API_PORT},
                     daemon=True).start()

    for rid in ("robot2", "robot4"):
        MockRobot(rid, rate=10.0, task_duration=1.5, broker_host=HOST,
                  broker_port=PORT, reject_when_idle=True).run_in_thread()

    inter = MqttTransport(client_id="interaction_sim")
    inter.connect(); inter.loop_start(); time.sleep(1.5)

    # ── 헬퍼 ─────────────────────────────────────────────────────────────
    def robot_state(rid):
        return {s["robot_id"]: s["state"] for s in reg.all_snapshots()}.get(rid)

    def mstate(mid):
        r = db.query_one("SELECT state FROM missions WHERE mission_id=?", (mid,))
        return r["state"] if r else None

    def latest():
        return db.query_one("SELECT * FROM missions ORDER BY created_at DESC LIMIT 1") or {}

    def transitions(mid):
        return [r["to_state"] for r in db.query_all(
            "SELECT to_state FROM mission_transitions WHERE mission_id=? ORDER BY id", (mid,))]

    def wait(pred, to=8.0):
        end = time.time() + to
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.1)
        return False

    def reset():
        wait(lambda: robot_state("robot2") == "PATROL" and robot_state("robot4") == "PATROL", to=6)

    def start_mission(reqid, dest_floor=2):
        inter.publish("mock/robot2/cmd", {"cmd": "call"}, qos=1)
        time.sleep(0.4)
        inter.publish(config.topic_request("robot2"),
                      messages.if01(reqid, "robot2", {"poi_id": "GATE_30", "floor": dest_floor},
                                    {"floor": 1, "pose": {"x": 0, "y": 0}}, {"profile": "GENERAL"}),
                      config.QOS_REQUEST)
        wait(lambda: latest().get("state") in ("ESCORTING_TO_HANDOVER", "HANDOVER_WAITING"), to=5)
        return latest().get("mission_id")

    failures = []

    def check(name, ok, detail=""):
        print(f"  {name}: {'PASS' if ok else 'FAIL'}{('  ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    print("[정상 흐름]")
    # 1) IF-02 파이프라인
    check("1) IF-02 파이프라인",
          wait(lambda: robot_state("robot2") == "PATROL" and robot_state("robot4") == "PATROL"))

    # 2) 층간 릴레이
    mid = start_mission("IT_RELAY", dest_floor=2)
    ok = wait(lambda: mstate(mid) == "COMPLETED", to=10)
    m = db.query_one("SELECT * FROM missions WHERE mission_id=?", (mid,)) or {}
    seq = transitions(mid)
    relay_ok = (ok and seq == ["ASSIGNED", "ESCORTING_TO_HANDOVER", "HANDOVER_WAITING",
                               "ESCORTING_TO_FINAL", "COMPLETED"]
                and m.get("handover_latency_ms") is not None)
    check("2) 층간 릴레이", relay_ok, f"latency={m.get('handover_latency_ms')}ms")
    reset()

    # 3) 같은 층 직행
    mid = start_mission("IT_SAMEFLOOR", dest_floor=1)
    ok = wait(lambda: mstate(mid) == "COMPLETED", to=8)
    seq = transitions(mid)
    check("3) 같은 층 직행",
          ok and seq == ["ASSIGNED", "ESCORTING_TO_FINAL", "COMPLETED"]
          and (db.query_one("SELECT handover_latency_ms h FROM missions WHERE mission_id=?", (mid,)) or {}).get("h") is None)
    reset()

    print("[예외 처리]")
    # 4) CANCEL
    mid = start_mission("IT_CANCEL")
    inter.publish(config.topic_request("robot2"),
                  messages.if01("IT_C", "robot2", {}, {}, request_type="CANCEL"), config.QOS_REQUEST)
    ok = wait(lambda: mstate(mid) == "CANCELLED", to=5)
    rb = db.query_all("SELECT 1 FROM tasks WHERE mission_id=? AND task_type='RETURN_TO_BASE'", (mid,))
    check("4) CANCEL", ok and len(rb) >= 1, f"복귀task {len(rb)}건")
    reset()

    # 5) EMERGENCY
    mid = start_mission("IT_EMG")
    inter.publish("mock/robot2/cmd", {"cmd": "emergency"}, qos=1)
    ok = wait(lambda: mstate(mid) == "EMERGENCY", to=5)
    t4 = db.query_all("SELECT 1 FROM tasks WHERE mission_id=? AND robot_id='robot4' "
                      "AND task_type='RETURN_TO_BASE'", (mid,))
    check("5) EMERGENCY", ok and len(t4) >= 1, "robot4 복귀")
    inter.publish("mock/robot2/cmd", {"cmd": "recover"}, qos=1)
    reset()

    # 6) task FAILED
    mid = start_mission("IT_FAIL")
    inter.publish("mock/robot2/cmd", {"cmd": "fail"}, qos=1)
    check("6) task FAILED", wait(lambda: mstate(mid) == "FAILED", to=5))
    inter.publish("mock/robot2/cmd", {"cmd": "recover"}, qos=1)
    reset()

    # 7) status timeout
    mid = start_mission("IT_TIMEOUT")
    inter.publish("mock/robot2/cmd", {"cmd": "mute"}, qos=1)
    check("7) status timeout", wait(lambda: mstate(mid) == "FAILED", to=8),
          f">{config.STATUS_TIMEOUT}s")
    inter.publish("mock/robot2/cmd", {"cmd": "recover"}, qos=1)

    print("[이상감지]")
    # 8) IF-05 (FIRE) → events 적재
    inter.publish(config.topic_event("robot2"),
                  messages.if05("robot2", "FIRE", 0.91,
                                {"x": 1.0, "y": 2.0, "floor": 1}, "img_demo.jpg"),
                  config.QOS_EVENT)
    ok = wait(lambda: db.query_one(
        "SELECT 1 FROM events WHERE event_type='FIRE' AND robot_id='robot2'") is not None, to=4)
    row = db.query_one("SELECT confidence, floor, snapshot_ref FROM events "
                       "WHERE event_type='FIRE' AND robot_id='robot2'") or {}
    check("8) IF-05 FIRE 적재", ok and row.get("confidence") == 0.91 and row.get("floor") == 1,
          f"conf={row.get('confidence')}, snapshot={row.get('snapshot_ref')}")

    print("[관제 API (읽기 전용 GET)]")

    # 로그인 가드가 생겼으므로 세션 쿠키로 인증 후 조회
    import http.cookiejar
    import urllib.parse
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    creds = urllib.parse.urlencode(
        {"user": config.ADMIN_USER, "password": config.ADMIN_PASSWORD}).encode()
    opener.open(f"http://127.0.0.1:{API_PORT}/login", data=creds, timeout=3)

    def api_get(path):
        return json.loads(opener.open(f"http://127.0.0.1:{API_PORT}{path}", timeout=3).read())

    robots = api_get("/api/robots")
    check("9) GET /api/robots", {r["robot_id"] for r in robots} == {"robot2", "robot4"})
    miss = api_get("/api/missions")
    check("10) GET /api/missions", len(miss["missions"]) >= 6,
          f"{len(miss['missions'])}건")
    evs = api_get("/api/events")
    check("11) GET /api/events", any(e["event_type"] == "FIRE" for e in evs))

    stop.set()
    fms.loop_stop(); fms.disconnect()
    inter.loop_stop(); inter.disconnect()

    print("=" * 50)
    if failures:
        print(f"❌ 실패 {len(failures)}건: {failures}")
        return 1
    print("✅ 통합 테스트 전체 PASS (정상 3 + 예외 4 + 이상감지 1 + 관제 API 3)")
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)  # 데몬 mock 스레드 즉시 종료
