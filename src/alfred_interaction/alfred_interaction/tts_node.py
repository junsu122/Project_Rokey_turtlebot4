#!/usr/bin/env python3
"""tts_node — 텍스트 → 음성.

▼ subs : /interaction/dialog
▲ pubs : 스피커 audio
TODO: TTS 엔진 연동, 음성 출력.
"""
import rclpy
from rclpy.node import Node


class TtsNode(Node):
    def __init__(self) -> None:
        super().__init__("tts_node")
        self.get_logger().info("tts_node 시작 (스켈레톤)")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TtsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
