#!/usr/bin/env python3
"""behavior_node — ★ Robot State 단독 소유. task 수행·자율 순찰.

▼ subs : /{ns}/fms/task (IF-03, 브리지가 재발행), /interaction/call, /safety/estop
▲ pubs : /{ns}/robot_state (IF-02), /{ns}/fms/task_ack, nav2 goal

핵심 규칙(계약):
  - Robot State는 이 노드만 소유·발행. FMS는 관측만.
  - task 없으면 자율 PATROL. FMS는 PATROL을 지시하지 않는다(절대 규칙 8).
  - 거절(§6.2): PATROL/IDLE에서 받은 ESCORT 계열 task는 REJECT.
  - 멱등: 처리한 task_id 재수신 무시.

TODO: 상태 기계(PATROL→…→RETURNING), nav2 액션 클라이언트, task_ack 발행,
      1~2Hz + 전이 시 즉시 robot_state 발행(핸드오버 3초 측정 전제).
"""
import rclpy
from rclpy.node import Node

from alfred_interfaces.msg import RobotState, Task, TaskAck


class BehaviorNode(Node):
    def __init__(self) -> None:
        super().__init__("behavior_node")
        self.declare_parameter("robot_id", "robot2")
        self.robot_id = self.get_parameter("robot_id").value
        self.state = "IDLE"  # Robot State 단독 소유

        self.pub_state = self.create_publisher(RobotState, f"/{self.robot_id}/robot_state", 10)
        self.pub_ack = self.create_publisher(TaskAck, f"/{self.robot_id}/fms/task_ack", 10)
        self.create_subscription(Task, f"/{self.robot_id}/fms/task", self._on_task, 10)
        self.get_logger().info(f"behavior_node 시작 (robot_id={self.robot_id}, 스켈레톤)")
        # TODO: 상태 발행 타이머, nav2 액션 클라이언트

    def _on_task(self, msg: Task) -> None:
        # TODO: 멱등 검사 → 상태별 ACCEPT/REJECT 판정 → task_ack 발행 → 수행
        self.get_logger().info(f"task 수신: {msg.task_id} ({msg.task_type}) — 처리 TODO")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BehaviorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
