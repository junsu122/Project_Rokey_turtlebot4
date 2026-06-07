#!/usr/bin/env python3
"""llm_node — 목적지 정규화·대화.

▼ subs : /interaction/stt_text
▲ pubs : /interaction/destination, /interaction/dialog
TODO: LLM 연동, 목적지 POI 정규화·검증.
"""
import rclpy
from rclpy.node import Node


class LlmNode(Node):
    def __init__(self) -> None:
        super().__init__("llm_node")
        self.get_logger().info("llm_node 시작 (스켈레톤)")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LlmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
