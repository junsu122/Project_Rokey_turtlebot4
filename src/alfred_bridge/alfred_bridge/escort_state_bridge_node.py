#!/usr/bin/env python3
"""escort_state_bridge_node — escort_node의 진행 상태를 관찰해 바뀔 때마다
behavior_node와 동일한 형식(alfred_interfaces/msg/RobotState)으로 publish한다
(rosbridge_websocket이 그대로 web client에 중계).

escort_node.py는 건드리지 않는다. 대신 그 노드가 구독하는 것과 동일한 토픽들
(/escort_request, /robot2/nav_status, /robot4/nav_status)을 관찰해서
escort_node.state(IDLE/TO_TRANSFER/WAITING/RETURNING)와 같은 전이를 거울처럼
재현한다. 목적지 → 담당 로봇 판단은 alfred_driving.locations.LOCATIONS를 그대로
참조해 escort_node와 동일한 결정(같은 층 vs 층 이동)을 보장한다.

publish:
    /escort_state (alfred_interfaces/msg/RobotState) — 상태가 바뀔 때만 발행
    behavior_node의 /robot2/robot_state와 같은 메시지 타입이라 web 쪽 파서를
    그대로 재사용할 수 있다. robot_id에는 단일 로봇이 아닌 2대 에스코트
    오케스트레이션이라는 점을 나타내기 위해 "escort"를 쓰고, 관련된 두 로봇은
    current_task_id에 "escort_robot->continue_robot" 형태로 담는다.

web에서 구독하려면 rosbridge에 이렇게 요청하면 된다(타입까지 동일):
    {"op": "subscribe", "topic": "/escort_state", "type": "alfred_interfaces/msg/RobotState"}
"""
from __future__ import annotations

from datetime import datetime, timezone

import rclpy
from geometry_msgs.msg import Pose2D
from rclpy.node import Node
from std_msgs.msg import String

from alfred_driving.locations import LOCATIONS
from alfred_interfaces.msg import RobotState

_HANDOFF_WAIT_SEC = 3.0  # escort_node.on_wait_complete와 동일한 핸드오버 대기 시간


class EscortStateBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__('escort_state_bridge_node')

        self.pub_state = self.create_publisher(RobotState, '/escort_state', 10)

        for robot in ('robot2', 'robot4'):
            self.create_subscription(
                String, f'/{robot}/nav_status',
                lambda msg, r=robot: self._on_nav_status(msg, r),
                10
            )
        self.create_subscription(String, '/escort_request', self._on_request, 10)

        # ---- escort_node.state를 거울처럼 재현하기 위한 내부 변수 ----
        self.state = "IDLE"
        self.pending_request: str | None = None
        self.escort_robot: str | None = None
        self.continue_robot: str | None = None
        self.arrived: dict[str, bool] = {}
        self.escort_stage: str | None = None
        self.continue_stage: str | None = None
        self.wait_timer = None

        self._publish_state()  # web이 시작 상태를 바로 알 수 있도록 최초 1회 발행
        self.get_logger().info("escort_state_bridge_node 시작 — /escort_state 로 변경 시 발행")

    # ---------- escort_node와 동일한 전이 로직(거울) ----------

    def _on_request(self, msg: String) -> None:
        goal_name = msg.data.strip()
        if goal_name not in LOCATIONS:
            return
        if self.state != "IDLE" or self.pending_request is not None:
            return
        self.pending_request = goal_name

    def _on_nav_status(self, msg: String, robot: str) -> None:
        if robot == 'robot2' and msg.data.startswith('patrol_stopped'):
            goal_name = self.pending_request
            if ':' in msg.data:
                goal_name = msg.data.split(':', 1)[1].strip()
            if goal_name is None or goal_name not in LOCATIONS:
                return
            self.pending_request = None
            self._start_escort(goal_name)
            return

        if msg.data != 'arrived':
            return

        if self.state == "TO_TRANSFER" and robot in self.arrived:
            self.arrived[robot] = True
            if all(self.arrived.values()):
                self._set_state("WAITING")
                self.wait_timer = self.create_timer(_HANDOFF_WAIT_SEC, self._on_wait_complete)

        elif self.state == "RETURNING":
            if robot == self.escort_robot and self.escort_stage == "TO_HOME":
                self.escort_stage = "DONE"
                self._try_finish()
            elif robot == self.continue_robot and self.continue_stage == "TO_GOAL":
                self.continue_stage = "TO_HOME"
            elif robot == self.continue_robot and self.continue_stage == "TO_HOME":
                self.continue_stage = "DONE"
                self._try_finish()

    def _start_escort(self, goal_name: str) -> None:
        goal = LOCATIONS[goal_name]
        if goal["robot"] == "robot2":
            return  # 같은 층 이동 — escort_node도 상태 전이 없이 IDLE 유지

        self.escort_robot = "robot2"
        self.continue_robot = goal["robot"]
        self.arrived = {self.escort_robot: False, self.continue_robot: False}
        self.escort_stage = None
        self.continue_stage = None
        self._set_state("TO_TRANSFER")

    def _on_wait_complete(self) -> None:
        self.wait_timer.cancel()
        self.wait_timer = None
        self.escort_stage = "TO_HOME"
        self.continue_stage = "TO_GOAL"
        self._set_state("RETURNING")

    def _try_finish(self) -> None:
        if self.escort_stage == "DONE" and self.continue_stage == "DONE":
            self._reset()

    def _reset(self) -> None:
        self.escort_robot = None
        self.continue_robot = None
        self.arrived = {}
        self.escort_stage = None
        self.continue_stage = None
        self._set_state("IDLE")

    # ---------- web으로 발행 ----------

    def _set_state(self, new_state: str) -> None:
        if new_state == self.state:
            return
        self.state = new_state
        self.get_logger().info(f"[escort_state] → {new_state}")
        self._publish_state()

    def _publish_state(self) -> None:
        # 관련된 두 로봇은 RobotState에 전용 필드가 없어 current_task_id에 담는다.
        if self.escort_robot and self.continue_robot:
            task_id = f"{self.escort_robot}->{self.continue_robot}"
        else:
            task_id = ""

        msg = RobotState()
        msg.robot_id = "escort"  # 단일 로봇이 아닌 2대 에스코트 오케스트레이션 상태
        msg.state = self.state
        msg.pose = Pose2D(x=0.0, y=0.0, theta=0.0)
        msg.battery = 0
        msg.current_task_id = task_id
        msg.task_status = ""
        msg.error_code = ""
        msg.timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.pub_state.publish(msg)


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
