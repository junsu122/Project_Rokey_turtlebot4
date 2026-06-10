#!/usr/bin/env python3
"""escort_state_bridge_node — escort/patrol/dock 상태를 관찰해 web에 push.

publish:
    /escort_state        (alfred_interfaces/msg/RobotState)  — FMS·모니터 공용
    /robot2/ui_state     (std_msgs/String, JSON)             — 1층 키오스크 UI (IF-02)
    /robot4/ui_state     (std_msgs/String, JSON)             — 2층 키오스크 UI (IF-02)

ui_state JSON: {"state","robot_id",[ "destination":{"poi_id"}, "target_floor" ]}
계약서: src/alfred_interaction/로봇상태_UI연동_계약.md (§2 토픽 / §5 상태 / §8 핸드오프)

지원 시나리오:
    1F→1F : robot2 단독 안내  PATROL→ESCORT_1F→ESCORT_COMPLETED→PATROL
    2F→2F : robot4 단독 안내  PATROL→ESCORT_2F→ESCORT_COMPLETED→PATROL
    1F→2F : 릴레이 안내
        PATROL→ESCORT_1F→WAITING_1F→ESCORT_1F_FINISHED→ESCORT_2F→ESCORT_COMPLETED→PATROL

Dock/charge cycle (patrol_node 배터리 저하 시):
    PATROL → DOCKING → UNDOCKING → PATROL
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import rclpy
from geometry_msgs.msg import Pose2D
from rclpy.node import Node
from std_msgs.msg import String

from alfred_driving.locations import LOCATIONS
from alfred_interfaces.msg import RobotState

_HANDOFF_WAIT_SEC = 3.0

# ── 상태 상수 ─────────────────────────────────────────────────────────────────
PATROL              = "PATROL"
ESCORT_1F           = "ESCORT_1F"
WAITING_1F          = "WAITING_1F"
WAITING_2F          = "WAITING_2F"
ESCORT_1F_FINISHED  = "ESCORT_1F_FINISHED"
ESCORT_2F           = "ESCORT_2F"
ESCORT_2F_FINISHED  = "ESCORT_2F_FINISHED"
ESCORT_COMPLETED    = "ESCORT_COMPLETED"
DOCKING             = "DOCKING"
UNDOCKING           = "UNDOCKING"
FIRE                = "FIRE"
INJURED             = "INJURED"
SUSPICIOUS          = "SUSPICIOUS"

EMERGENCY_STATES    = frozenset({FIRE, INJURED, SUSPICIOUS})

_DETECTION_STATE_MAP = {
    'FIRE':              FIRE,
    'INJURED_PERSON':    INJURED,
    'SUSPICIOUS_PERSON': SUSPICIOUS,
}


class EscortStateBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__('escort_state_bridge_node')

        self.pub_state = self.create_publisher(RobotState, '/escort_state', 10)

        self._ui_pubs = {
            'robot2': self.create_publisher(String, '/robot2/ui_state', 10),
            'robot4': self.create_publisher(String, '/robot4/ui_state', 10),
        }
        self._ui_last: dict[str, str] = {}

        for robot in ('robot2', 'robot4'):
            self.create_subscription(
                String, f'/{robot}/nav_status',
                lambda msg, r=robot: self._on_nav_status(msg, r),
                10,
            )
            self.create_subscription(
                String, f'/{robot}/detection/info',
                lambda msg, r=robot: self._on_detection(msg, r),
                10,
            )
        self.create_subscription(String, '/escort_request', self._on_request, 10)
        self.create_subscription(String, '/information', self._on_information, 10)

        # 내부 추적 변수
        self.state: str = PATROL
        self.pending_request: str | None = None   # /escort_request 단일 단계용
        self._waiting_for_dest: bool = False      # STOP→ESCORT 2단계 웹 흐름용
        self.escort_robot: str | None = None      # 1F 안내 로봇 (robot2 or None)
        self.continue_robot: str | None = None    # 2F 안내 로봇 (robot4 or None)
        self.arrived: dict[str, bool] = {}
        self.escort_stage: str | None = None
        self.continue_stage: str | None = None
        self.wait_timer = None
        self._dock_robot: str | None = None
        self.goal_poi: str | None = None
        self._emergency_robot: str | None = None

        self._publish_state()
        self._route_ui(PATROL)
        self.get_logger().info(
            "escort_state_bridge_node 시작 — 1F→1F / 2F→2F / 1F→2F 모두 지원"
        )

    # ── 요청 콜백 ─────────────────────────────────────────────────────────────

    def _on_request(self, msg: String) -> None:
        """단일 단계 /escort_request (비-web 흐름)."""
        goal_name = msg.data.strip()
        if goal_name not in LOCATIONS:
            return
        if self.state != PATROL or self.pending_request is not None:
            return
        self.pending_request = goal_name

    def _on_information(self, msg: String) -> None:
        """웹 /information STOP·ESCORT 2단계 흐름 처리."""
        try:
            envelope = json.loads(msg.data)
        except (TypeError, json.JSONDecodeError):
            return
        payload = envelope.get('msg', envelope)
        if not isinstance(payload, dict):
            return
        request_type = payload.get('request_type', '')

        if request_type in ('STOP', 'INTERACTING'):
            if self.state == PATROL and not self._waiting_for_dest:
                self._waiting_for_dest = True

        elif request_type == 'ESCORT':
            poi_id = (payload.get('destination') or {}).get('poi_id')
            if not poi_id or poi_id not in LOCATIONS:
                return
            goal = LOCATIONS[poi_id]

            if self._waiting_for_dest:
                # robot2 정지 후 목적지 수신 → 1F→1F 또는 1F→2F
                self._waiting_for_dest = False
                self._start_escort(poi_id)
            elif self.state == PATROL and goal['robot'] == 'robot4':
                # robot2 정지 없이 2F 목적지 → 2F→2F
                self._start_escort(poi_id)

    def _on_detection(self, msg: String, robot: str) -> None:
        """detector_node 의 /{robot}/detection/info → FIRE/INJURED/SUSPICIOUS 상태 전이."""
        if self.state != PATROL:
            return
        try:
            payload = json.loads(msg.data)
        except (TypeError, json.JSONDecodeError):
            return
        new_state = _DETECTION_STATE_MAP.get(payload.get('event_type', ''))
        if new_state is None:
            return
        self._emergency_robot = robot
        self._set_state(new_state)

    # ── nav_status 콜백 ───────────────────────────────────────────────────────

    def _on_nav_status(self, msg: String, robot: str) -> None:
        data = msg.data

        # ── 도킹/언도킹 ──────────────────────────────────────────────────────
        if data == 'docking' and self.state == PATROL:
            self._dock_robot = robot
            self._set_state(DOCKING)
            return

        if data == 'undocking' and self.state in (DOCKING, PATROL):
            self._set_state(UNDOCKING)
            return

        if data == 'patrol_resumed':
            if self.state in EMERGENCY_STATES:
                # fire/injured/suspicious 핸들러가 비상 처리 완료 → PATROL 복귀
                self._emergency_robot = None
                self._waiting_for_dest = False
                self._set_state(PATROL)
                return
            if self.state == UNDOCKING:
                self._dock_robot = None
                self._set_state(PATROL)
                return

        # ── 에스코트 시작 (patrol_stopped) ───────────────────────────────────
        if data.startswith('patrol_stopped'):
            # Emergency 핸들러가 정지시킨 경우 → escort 흐름 무시
            if self.state in EMERGENCY_STATES:
                return
            goal_name = self.pending_request
            if ':' in data:
                goal_name = data.split(':', 1)[1].strip()

            if goal_name and goal_name in LOCATIONS:
                # 단일 단계(/escort_request): 목적지 포함
                self.pending_request = None
                self._waiting_for_dest = False
                self._start_escort(goal_name)
            elif robot == 'robot2':
                # 2단계 웹 흐름: 목적지 아직 미수신, ESCORT 메시지 대기
                self._waiting_for_dest = True
            return

        # ── arrived 처리 ──────────────────────────────────────────────────────
        if data != 'arrived':
            return

        # 1F→1F: robot2 목적지 도착
        if self.state == ESCORT_1F and self.escort_stage == 'TO_GOAL':
            if robot == self.escort_robot:
                self._finish_escort()
            return

        # 1F→2F: robot2 환승점 도착
        if self.state == ESCORT_1F and robot in self.arrived:
            self.arrived[robot] = True
            if all(self.arrived.values()):
                self._set_state(WAITING_1F)
                self.wait_timer = self.create_timer(_HANDOFF_WAIT_SEC, self._on_wait_complete)
            return

        # 2F 안내 중 도착 처리
        if self.state in (ESCORT_2F, ESCORT_2F_FINISHED):
            if self.escort_robot and robot == self.escort_robot and self.escort_stage == 'TO_HOME':
                self.escort_stage = 'DONE'
                self._try_finish()
            elif self.continue_robot and robot == self.continue_robot:
                if self.continue_stage == 'TO_GOAL':
                    self.continue_stage = 'TO_HOME'
                    self._set_state(ESCORT_2F_FINISHED)
                elif self.continue_stage == 'TO_HOME':
                    self.continue_stage = 'DONE'
                    self._try_finish()
            return

    # ── 에스코트 상태 전이 ────────────────────────────────────────────────────

    def _start_escort(self, goal_name: str) -> None:
        goal = LOCATIONS[goal_name]
        self.goal_poi = goal_name

        if goal['robot'] == 'robot2':
            # 1F→1F: robot2 단독
            self.escort_robot  = 'robot2'
            self.continue_robot = None
            self.escort_stage  = 'TO_GOAL'
            self.continue_stage = 'DONE'
            self.arrived       = {}
            self._set_state(ESCORT_1F)

        elif self.state == PATROL and not self._waiting_for_dest:
            # 2F→2F: robot4 단독 (robot2 정지 없음)
            self.escort_robot   = None
            self.continue_robot = 'robot4'
            self.escort_stage   = 'DONE'
            self.continue_stage = 'TO_GOAL'
            self.arrived        = {}
            self._set_state(ESCORT_2F)

        else:
            # 1F→2F: robot2→환승점, robot4→환승점
            self.escort_robot   = 'robot2'
            self.continue_robot = 'robot4'
            self.escort_stage   = None
            self.continue_stage = None
            self.arrived        = {'robot2': False}  # robot4는 ESCORT_1F 중 미이동
            self._set_state(ESCORT_1F)

        self.get_logger().info(
            f"[start_escort] {goal_name} | "
            f"escort={self.escort_robot} continue={self.continue_robot}"
        )

    def _on_wait_complete(self) -> None:
        """WAITING_1F 대기 종료 → robot4 2F 안내 시작."""
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.escort_stage   = 'TO_HOME'
        self.continue_stage = 'TO_GOAL'
        self._set_state(ESCORT_1F_FINISHED)
        self._set_state(ESCORT_2F)

    def _finish_escort(self) -> None:
        """1F→1F / 2F→2F 단일 로봇 안내 완료."""
        self._set_state(ESCORT_COMPLETED)
        self._set_state(PATROL)
        self.escort_robot   = None
        self.continue_robot = None
        self.escort_stage   = None
        self.continue_stage = None
        self.goal_poi       = None

    def _try_finish(self) -> None:
        if self.escort_stage == 'DONE' and self.continue_stage == 'DONE':
            self._reset()

    def _reset(self) -> None:
        # 상태 전이 먼저 (route_ui가 escort/continue_robot 참조)
        self._set_state(ESCORT_COMPLETED)
        self._set_state(PATROL)
        self.escort_robot   = None
        self.continue_robot = None
        self.arrived        = {}
        self.escort_stage   = None
        self.continue_stage = None
        self.goal_poi       = None

    # ── 발행 ──────────────────────────────────────────────────────────────────

    def _set_state(self, new_state: str) -> None:
        if new_state == self.state:
            return
        old = self.state
        self.state = new_state
        self.get_logger().info(f"[escort_state] {old} → {new_state}")
        self._publish_state()
        self._route_ui(new_state)

    def _publish_state(self) -> None:
        if self.escort_robot and self.continue_robot:
            task_id = f"{self.escort_robot}->{self.continue_robot}"
        elif self._dock_robot:
            task_id = self._dock_robot
        elif self.escort_robot:
            task_id = self.escort_robot
        elif self.continue_robot:
            task_id = self.continue_robot
        else:
            task_id = ""

        msg = RobotState()
        msg.robot_id        = "escort"
        msg.state           = self.state
        msg.pose            = Pose2D(x=0.0, y=0.0, theta=0.0)
        msg.battery         = 0
        msg.current_task_id = task_id
        msg.task_status     = ""
        msg.error_code      = ""
        msg.timestamp       = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.pub_state.publish(msg)

    # ── ui_state 라우팅 ───────────────────────────────────────────────────────

    def _route_ui(self, state: str) -> None:
        dest = {"poi_id": self.goal_poi} if self.goal_poi else None

        if state == ESCORT_1F:
            if self.escort_robot:
                self._publish_ui(self.escort_robot, ESCORT_1F, destination=dest)

        elif state == WAITING_1F:
            self._publish_ui("robot2", WAITING_1F)
            self._publish_ui("robot4", WAITING_2F)

        elif state == ESCORT_1F_FINISHED:
            self._publish_ui("robot2", ESCORT_1F_FINISHED, target_floor=2)

        elif state == ESCORT_2F:
            if self.continue_robot:
                self._publish_ui(self.continue_robot, ESCORT_2F, destination=dest)

        elif state == ESCORT_2F_FINISHED:
            # 사용자 2F 도착 완료 → 해당 로봇 키오스크에 ESCORT_COMPLETED 표시
            if self.continue_robot:
                self._publish_ui(self.continue_robot, ESCORT_COMPLETED)

        elif state == ESCORT_COMPLETED:
            # 단일 로봇 완료(1F→1F / 2F→2F) or 릴레이 최종 완료
            robot = self.continue_robot or self.escort_robot
            if robot:
                self._publish_ui(robot, ESCORT_COMPLETED)

        elif state == DOCKING:
            self._publish_ui(self._dock_robot or "robot2", DOCKING)

        elif state == UNDOCKING:
            self._publish_ui(self._dock_robot or "robot2", UNDOCKING)

        elif state in EMERGENCY_STATES:
            robot = self._emergency_robot or 'robot2'
            self._publish_ui(robot, state)

        elif state == PATROL:
            self._publish_ui("robot2", PATROL)
            self._publish_ui("robot4", PATROL)

    def _publish_ui(self, robot_id: str, state: str, **fields) -> None:
        payload: dict = {"state": state, "robot_id": robot_id}
        for key, value in fields.items():
            if value is not None:
                payload[key] = value
        snapshot = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        topic = f"/{robot_id}/ui_state"
        if self._ui_last.get(topic) == snapshot:
            return
        self._ui_last[topic] = snapshot
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._ui_pubs[robot_id].publish(msg)
        self.get_logger().info(f"[ui_state] {topic} ← {msg.data}")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = EscortStateBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
