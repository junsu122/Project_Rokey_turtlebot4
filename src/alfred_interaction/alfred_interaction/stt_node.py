#!/usr/bin/env python3
"""stt_node — 음성 → 텍스트.

▼ subs : 마이크 audio
▲ pubs : /interaction/stt_text
TODO: STT 엔진(로컬/클라우드) 연동, 텍스트 발행.
"""
import rclpy
from rclpy.node import Node


class SttNode(Node):
    def __init__(self) -> None:
        super().__init__("stt_node")
        self.get_logger().info("stt_node 시작 (스켈레톤)")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SttNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
