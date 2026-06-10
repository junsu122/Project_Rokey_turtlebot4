#!/usr/bin/env python3
"""robot_state_publisher_node — amcl_pose + battery_state → /{robot}/robot_state

behavior_node 미구현 기간 동안 로봇의 실시간 위치·배터리를
monitor_server가 읽을 수 있는 RobotState 메시지로 변환해 1 Hz로 발행한다.

state 전이:
  기본값             PATROL
  patrol_stopped   INTERACTING   (고객 응대 / 목적지 대기)
  goal_pose_request ESCORTING    (에스코트 이동 중)
  resume_patrol    PATROL        (에스코트 완료 후 순찰 복귀)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Empty, String

from alfred_interfaces.msg import RobotState


ROBOTS = ["robot2", "robot4"]


class RobotStatePublisherNode(Node):
    def __init__(self) -> None:
        super().__init__("robot_state_publisher_node")

        self._pose: dict[str, tuple[float, float, float]] = {r: (0.0, 0.0, 0.0) for r in ROBOTS}
        self._battery: dict[str, int] = {r: -1 for r in ROBOTS}
        self._state: dict[str, str] = {r: "PATROL" for r in ROBOTS}
        self._pubs: dict[str, rclpy.publisher.Publisher] = {}

        for robot in ROBOTS:
            self._pubs[robot] = self.create_publisher(
                RobotState, f"/{robot}/robot_state", 10
            )
            self.create_subscription(
                PoseWithCovarianceStamped,
                f"/{robot}/amcl_pose",
                lambda msg, r=robot: self._on_amcl_pose(msg, r),
                10,
            )
            self.create_subscription(
                BatteryState,
                f"/{robot}/battery_state",
                lambda msg, r=robot: self._on_battery(msg, r),
                10,
            )
            self.create_subscription(
                String,
                f"/{robot}/nav_status",
                lambda msg, r=robot: self._on_nav_status(msg, r),
                10,
            )
            self.create_subscription(
                Empty,
                f"/{robot}/resume_patrol_request",
                lambda _msg, r=robot: self._on_resume(r),
                10,
            )
            self.create_subscription(
                PoseStamped,
                f"/{robot}/goal_pose_request",
                lambda _msg, r=robot: self._on_goal(r),
                10,
            )

        self.create_timer(1.0, self._publish_all)
        self.get_logger().info("robot_state_publisher_node started")

    # ── 콜백 ────────────────────────────────────────────────────────────────

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped, robot: str) -> None:
        p = msg.pose.pose
        yaw = _yaw_from_quaternion(p.orientation)
        self._pose[robot] = (p.position.x, p.position.y, yaw)

    def _on_battery(self, msg: BatteryState, robot: str) -> None:
        if msg.percentage >= 0.0:
            self._battery[robot] = int(msg.percentage * 100)

    def _on_nav_status(self, msg: String, robot: str) -> None:
        if msg.data.startswith("patrol_stopped"):
            self._state[robot] = "INTERACTING"

    def _on_goal(self, robot: str) -> None:
        if self._state[robot] == "INTERACTING":
            self._state[robot] = "ESCORTING"

    def _on_resume(self, robot: str) -> None:
        self._state[robot] = "PATROL"

    # ── 발행 ────────────────────────────────────────────────────────────────

    def _publish_all(self) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        for robot in ROBOTS:
            x, y, theta = self._pose[robot]
            msg = RobotState()
            msg.robot_id = robot
            msg.state = self._state[robot]
            msg.pose.x = x
            msg.pose.y = y
            msg.pose.theta = theta
            msg.battery = self._battery[robot]
            msg.current_task_id = ""
            msg.task_status = ""
            msg.error_code = ""
            msg.timestamp = now
            self._pubs[robot].publish(msg)


def _yaw_from_quaternion(q) -> float:
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RobotStatePublisherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
