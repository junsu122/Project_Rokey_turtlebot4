#!/usr/bin/env python3
"""video_sender_node — (향후·선택) 카메라 라이브 영상 송신.

▼ subs : /camera/image
→ WebRTC 등으로 관리자 UI에 직접(데이터 평면, FMS/브리지 우회).
TODO: WebRTC / web_video_server 연동.
"""
import rclpy
from rclpy.node import Node


class VideoSenderNode(Node):
    def __init__(self) -> None:
        super().__init__("video_sender_node")
        self.get_logger().info("video_sender_node 시작 (스켈레톤·선택 기능)")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VideoSenderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
