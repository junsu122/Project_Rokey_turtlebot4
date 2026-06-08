"""FMS 서버 조립·기동 (구현가이드 §3).

기동 책임: MQTT 연결, (M1+)구독 핸들러 연결, Flask 스레드, 타임아웃 감시 스레드.
현재 단계(M0): db 초기화 + MQTT 연결까지. 이벤트 핸들러/FSM/API는 후속 마일스톤에서 연결.

절대 규칙 2: 블로킹 대기 금지. main은 MQTT 백그라운드 루프를 띄우고 신호 대기만 한다.
            "로봇 도착까지 기다리는" 절차적 흐름을 main에 두지 않는다.
"""

from __future__ import annotations

import logging
import signal
import threading

import api
import config
import db
import event_service
from mission_manager import MissionManager
from robot_registry import RobotRegistry
from transport import MqttTransport


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("fms.main")


class FmsServer:
    def __init__(self) -> None:
        self.transport = MqttTransport()
        self.registry = RobotRegistry()
        self.missions = MissionManager(self.transport, self.registry)
        self._stop = threading.Event()

    def start(self) -> None:
        db.init_db()
        logger.info("SQLite ready (WAL): %s", config.DB_PATH)

        self.transport.connect()
        self.transport.loop_start()

        # ── 로봇→FMS 채널 구독 (와일드카드) ─────────────────────────────
        self.transport.subscribe(
            config.TOPIC_STATUS_WILDCARD, self._on_status, config.QOS_STATUS)
        self.transport.subscribe(
            config.TOPIC_REQUEST_WILDCARD, self._on_request, config.QOS_REQUEST)
        self.transport.subscribe(
            config.TOPIC_TASK_ACK_WILDCARD, self._on_ack, config.QOS_TASK_ACK)
        self.transport.subscribe(
            config.TOPIC_EVENT_WILDCARD, self._on_event, config.QOS_EVENT)

        # ── Flask 조회 스레드 (읽기 전용) ───────────────────────────────
        threading.Thread(
            target=api.run_api, args=(self.registry,), daemon=True,
            name="flask-api").start()

        # ── 타임아웃 감시 스레드 (절대 규칙 2: sleep 흐름 아닌 주기 체크) ──
        threading.Thread(
            target=self._watch_status_timeout, daemon=True,
            name="status-watch").start()

        logger.info("FMS M3 ready — mission FSM + 예외처리 + 타임아웃 감시 + 조회 API")

    # ── 핸들러 (paho 단일 콜백 스레드에서 순차 실행) ─────────────────────
    def _on_status(self, _topic: str, payload: dict) -> None:
        self.registry.update_from_status(payload)   # 관측·기록
        self.missions.on_robot_status(payload)      # 전이 진행

    def _on_request(self, _topic: str, payload: dict) -> None:
        self.missions.on_request(payload)

    def _on_ack(self, _topic: str, payload: dict) -> None:
        self.missions.on_task_ack(payload)

    def _on_event(self, _topic: str, payload: dict) -> None:
        event_service.record_event(payload)   # IF-05 적재(미션과 무관)

    def _watch_status_timeout(self) -> None:
        """주기적으로 status 미수신 로봇을 점검(폴링-데이터 아님, 감시 타이머)."""
        while not self._stop.is_set():
            try:
                self.missions.check_timeouts()
            except Exception:
                logger.exception("status timeout watch error")
            # sleep이 아니라 종료 이벤트 대기 — 종료 시 즉시 깨어남
            self._stop.wait(config.STATUS_WATCH_INTERVAL)

    def stop(self) -> None:
        logger.info("FMS shutting down")
        self.transport.loop_stop()
        self.transport.disconnect()
        db.close()
        self._stop.set()

    def run_forever(self) -> None:
        self.start()
        signal.signal(signal.SIGINT, lambda *_: self.stop())
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        self._stop.wait()  # 블로킹 sleep 아님 — 종료 신호까지 이벤트 대기


def main() -> None:
    FmsServer().run_forever()


if __name__ == "__main__":
    main()
