"""가짜 로봇 시뮬레이터 — 실로봇 없이 FMS 전체를 검증하는 핵심 도구 (구현가이드 M1).

동작:
- IF-02를 주기(기본 1Hz) 발행. 상태 전이 시 즉시 발행(핸드오버 3초 측정 전제).
- robot/{id}/task 구독 → ACK(기본 ACCEPT) → N초 뒤 task_status=SUCCEEDED + 상태 전이 보고.
- ROS를 쓰지 않는다(MQTT만) → 실브리지와 같은 토픽/페이로드 규약. 도메인 구성과 무관.

실행 예:
    python3 tools/mock_robot.py --robot-id robot2
    python3 tools/mock_robot.py --robot-id robot4 --rate 5 --task-duration 3

인자 규약(--robot-id/--namespace/--ros-domain-id)은 실브리지 런처와 동일하게 맞춰,
공유 도메인(현재)·분리 도메인(월요일)·실로봇 교체를 "실행 인자만 바꿔" 다룬다.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import messages  # noqa: E402
import states  # noqa: E402
from transport import MqttTransport  # noqa: E402


logger = logging.getLogger("mock_robot")

# task 수행 중(in-progress) 보고할 Robot State
TASK_PROGRESS_STATE = {
    states.TASK_MOVE_TO_STANDBY: states.ROBOT_RESERVED,
    states.TASK_ESCORT_TO_HANDOVER: states.ROBOT_ESCORTING,
    states.TASK_ESCORT_TO_FINAL: states.ROBOT_ESCORTING,
    states.TASK_RETURN_TO_BASE: states.ROBOT_RETURNING,
}
# task 완료(SUCCEEDED) 시 전이할 Robot State (전이표 §7 기준)
TASK_DONE_STATE = {
    states.TASK_MOVE_TO_STANDBY: states.ROBOT_HANDOVER_READY,
    states.TASK_ESCORT_TO_HANDOVER: states.ROBOT_WAITING_HANDOVER,
    states.TASK_ESCORT_TO_FINAL: states.ROBOT_ESCORTING,   # 이후 FMS가 RETURN_TO_BASE
    states.TASK_RETURN_TO_BASE: states.ROBOT_PATROL,        # task 완전 종료 → 순찰 복귀
}


class MockRobot:
    def __init__(self, robot_id: str, rate: float, task_duration: float,
                 broker_host: str, broker_port: int, reject_when_idle: bool,
                 pose: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        self.robot_id = robot_id
        self.period = 1.0 / max(rate, 0.1)
        self.task_duration = task_duration
        self.reject_when_idle = reject_when_idle
        self.transport = MqttTransport(
            host=broker_host, port=broker_port, client_id=f"mock_{robot_id}")

        self._lock = threading.Lock()
        # 초기 상태: task 없는 기본 동작 = 순찰 (절대 규칙 8: FMS가 시키지 않음)
        self.state = states.ROBOT_PATROL
        self.battery = 100
        # 맵 위에 표시될 좌표(데모용). 실로봇은 실제 pose를 보고함.
        self.pose = {"x": pose[0], "y": pose[1], "theta": pose[2]}
        self.current_task_id: str | None = None
        self.task_type: str | None = None
        self.task_status: str | None = None
        self._task_done_at: float | None = None
        self._muted = False  # 통신두절 시뮬레이션(테스트): IF-02 발행 중단

    def run_in_thread(self) -> threading.Thread:
        """데몬 스레드로 start() 구동 — 통합 테스트 등에서 여러 대를 띄울 때."""
        t = threading.Thread(target=self.start, daemon=True, name=f"mock-{self.robot_id}")
        t.start()
        return t

    def start(self) -> None:
        self.transport.connect()
        self.transport.loop_start()
        self.transport.subscribe(
            config.topic_task(self.robot_id), self._on_task, config.QOS_TASK)
        # 테스트 전용 제어 채널(계약 외): 고객 호출 재현용.
        #   {"cmd":"call"} → PATROL→INTERACTING (호출받아 응대 중)
        #   {"cmd":"idle"} → PATROL 복귀
        self.transport.subscribe(
            f"mock/{self.robot_id}/cmd", self._on_cmd, qos=1)
        logger.info("mock %s online (rate=%.1fHz, task=%.1fs) → broker %s:%s",
                    self.robot_id, 1.0 / self.period, self.task_duration,
                    self.transport.host, self.transport.port)
        self._publish_status()  # 초기 1회 즉시 발행
        try:
            while True:
                if self._maybe_complete_task():
                    pass  # 완료 시 상태가 바뀐 채로 아래에서 즉시 발행됨
                self._publish_status()
                time.sleep(self.period)
        except KeyboardInterrupt:
            logger.info("mock %s shutting down", self.robot_id)
        finally:
            self.transport.loop_stop()
            self.transport.disconnect()

    # ── 테스트 제어(고객 호출/예외 주입 재현) ───────────────────────────
    def _on_cmd(self, _topic: str, payload: dict) -> None:
        cmd = payload.get("cmd")
        with self._lock:
            if cmd == "call" and self.current_task_id is None:
                self.state = states.ROBOT_INTERACTING
            elif cmd == "idle" and self.current_task_id is None:
                self.state = states.ROBOT_PATROL
            elif cmd == "emergency":
                # 비상정지: 진행 중 task 멈추고 EMERGENCY 보고(상태는 로봇 소유)
                self.state = states.ROBOT_EMERGENCY
                self.task_status = None
                self._task_done_at = None
            elif cmd == "fail":
                # 현재 task 실패 보고
                if self.current_task_id is not None:
                    self.task_status = states.TS_FAILED
                    self._task_done_at = None
            elif cmd == "recover":
                self.state = states.ROBOT_PATROL
                self.current_task_id = None
                self.task_status = None
                self._task_done_at = None
                self._muted = False
            elif cmd == "mute":      # 통신두절: IF-02 발행 중단
                self._muted = True
            elif cmd == "unmute":
                self._muted = False
        logger.info("mock %s ◀ cmd=%s → state %s (muted=%s)",
                    self.robot_id, cmd, self.state, self._muted)
        self._publish_status()

    # ── IF-03 task 수신 ─────────────────────────────────────────────────
    def _on_task(self, _topic: str, payload: dict) -> None:
        task_id = payload.get("task_id")
        task_type = payload.get("task_type")
        logger.info("mock %s ◀ task %s (%s)", self.robot_id, task_id, task_type)

        # 거절 규칙(계약 §6.2): ESCORT 계열인데 로봇이 PATROL/IDLE(임무 없이 복귀)이면 REJECT.
        # → 유령 에스코트(고객이 떠난 뒤 지연 도착 task) 방지. HANDOVER_READY 등 임무 중 상태는 수락.
        result = states.ACK_ACCEPT
        with self._lock:
            cur = self.state
        if (self.reject_when_idle
                and task_type in states.ESCORT_TASK_TYPES
                and cur in {states.ROBOT_PATROL, states.ROBOT_IDLE}):
            result = states.ACK_REJECT

        self.transport.publish(
            config.topic_task_ack(self.robot_id),
            messages.task_ack(task_id, self.robot_id, result),
            config.QOS_TASK_ACK)
        logger.info("mock %s ▶ ack %s = %s", self.robot_id, task_id, result)
        if result == states.ACK_REJECT:
            return

        with self._lock:
            self.current_task_id = task_id
            self.task_type = task_type
            self.task_status = states.TS_RUNNING
            self.state = TASK_PROGRESS_STATE.get(task_type, self.state)
            self._task_done_at = time.time() + self.task_duration
        self._publish_status()  # RUNNING 전이 즉시 발행

    def _maybe_complete_task(self) -> bool:
        with self._lock:
            if self._task_done_at is None or time.time() < self._task_done_at:
                return False
            task_type = self.task_type
            self.task_status = states.TS_SUCCEEDED
            self.state = TASK_DONE_STATE.get(task_type, self.state)
            self._task_done_at = None
            if task_type == states.TASK_RETURN_TO_BASE:
                # task 완전 종료 → 기본 동작(순찰), current_task_id=null
                self.current_task_id = None
                self.task_status = None
            done_type, done_state = task_type, self.state
        logger.info("mock %s ✓ %s SUCCEEDED → state %s",
                    self.robot_id, done_type, done_state)
        return True

    def _publish_status(self) -> None:
        if self._muted:
            return  # 통신두절 시뮬레이션 — FMS 타임아웃 감시 검증용
        with self._lock:
            msg = messages.if02(
                self.robot_id, self.state, dict(self.pose), self.battery,
                self.current_task_id, self.task_status)
        self.transport.publish(
            config.topic_status(self.robot_id), msg, config.QOS_STATUS)


def main() -> int:
    parser = argparse.ArgumentParser(description="FMS mock robot (MQTT-only simulator)")
    parser.add_argument("--robot-id", required=True, help="예: robot2, robot4")
    parser.add_argument("--rate", type=float, default=1.0, help="IF-02 발행 주기(Hz)")
    parser.add_argument("--task-duration", type=float, default=3.0,
                        help="task 접수 후 SUCCEEDED까지(초)")
    parser.add_argument("--broker-host", default=config.MQTT_HOST)
    parser.add_argument("--broker-port", type=int, default=config.MQTT_PORT)
    parser.add_argument("--reject-when-idle", action="store_true",
                        help="ESCORT task를 INTERACTING/ESCORTING 아닐 때 거절(계약 §6.2)")
    parser.add_argument("--start-x", type=float, default=0.0, help="맵 표시용 시작 x(m)")
    parser.add_argument("--start-y", type=float, default=0.0, help="맵 표시용 시작 y(m)")
    parser.add_argument("--theta", type=float, default=0.0, help="시작 헤딩(rad)")
    # 실브리지 런처와 인자 규약 정합용(정보 필드 — mock은 MQTT만 사용)
    parser.add_argument("--namespace", default=None, help="(정보용) ROS 네임스페이스")
    parser.add_argument("--ros-domain-id", default=None, help="(정보용) ROS_DOMAIN_ID")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    MockRobot(
        robot_id=args.robot_id,
        rate=args.rate,
        task_duration=args.task_duration,
        broker_host=args.broker_host,
        broker_port=args.broker_port,
        reject_when_idle=args.reject_when_idle,
        pose=(args.start_x, args.start_y, args.theta),
    ).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
