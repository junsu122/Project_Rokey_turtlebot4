#!/usr/bin/env python3
"""yolo_monitor_node — 순찰 중 이상감지(FIRE / SUSPICIOUS_PERSON).

▼ subs : /camera/image
▲ pubs : /{ns}/vision/alert (IF-05 Event)
TODO: YOLO 추론, 임계치 판정 → Event.msg 발행.
"""
import rclpy
from rclpy.node import Node

from alfred_interfaces.msg import Event


class YoloMonitorNode(Node):
    def __init__(self) -> None:
        super().__init__("yolo_monitor_node")
        self.declare_parameter("robot_id", "robot2")
        self.robot_id = self.get_parameter("robot_id").value
        self.pub_alert = self.create_publisher(Event, f"/{self.robot_id}/vision/alert", 10)
        self.get_logger().info(f"yolo_monitor_node 시작 (robot_id={self.robot_id}, 스켈레톤)")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = YoloMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
