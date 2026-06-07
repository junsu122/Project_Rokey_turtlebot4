#!/usr/bin/env python3
"""ui_node — 터치스크린·얼굴·Q/A. 고객 호출 수신, IF-01 요청 발행.

▼ subs : /{ns}/robot_state, /interaction/dialog
▲ pubs : /{ns}/ui/request (IF-01 Request), /interaction/call
TODO: UI 이벤트 → Request.msg 생성·발행, robot_state 표시.
"""
import rclpy
from rclpy.node import Node


class UiNode(Node):
    def __init__(self) -> None:
        super().__init__("ui_node")
        self.get_logger().info("ui_node 시작 (스켈레톤)")
        # TODO: publisher/subscriber 구성


def main(args=None) -> None:
    rclpy.init(args=args)
    node = UiNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
