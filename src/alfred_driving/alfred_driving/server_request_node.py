#!/usr/bin/env python3
"""웹 정보를 받아 정규화된 시나리오 요청으로 발행한다.

이 노드는 의도적으로 작게 유지한다. 서버/웹 입력을 ROS 토픽으로 넘기는
역할만 담당하며, 시나리오 판단은 scenario_manager_node와 scenario_planner.py가 담당한다.
"""

from __future__ import annotations

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ServerRequestNode(Node):
    def __init__(self):
        super().__init__('server_request_node')
        #웹에서 주는 토픽이름
        self.declare_parameter('input_topic', '/information')
        # Flitering 후 보낼 토픽이름
        self.declare_parameter('output_topic', '/scenario_request')

        input_topic = str(self.get_parameter('input_topic').value)
        output_topic = str(self.get_parameter('output_topic').value)

        self._pub = self.create_publisher(String, output_topic, 10)
        self.create_subscription(String, input_topic, self._on_information, 10)

        self.get_logger().info(f'server_request_node ready: {input_topic} -> {output_topic}')

    def _on_information(self, msg: String):
        try:
            envelope = json.loads(msg.data)
            payload = normalize_information_payload(envelope)
        except (TypeError, ValueError, json.JSONDecodeError) as err:
            self.get_logger().warn(f'Ignoring invalid server information: {err}')
            return

        if not isinstance(payload, dict):
            self.get_logger().warn('Ignoring /information payload that is not a JSON object')
            return

        out = String()
        out.data = json.dumps(payload, ensure_ascii=False)
        self._pub.publish(out)


def normalize_information_payload(value):
    """Accept raw IF-01, rosbridge envelope, or std_msgs/String-wrapped JSON."""
    payload = value.get('msg', value) if isinstance(value, dict) else value

    if isinstance(payload, dict) and isinstance(payload.get('data'), str):
        data = payload['data'].strip()
        if data.startswith('{'):
            payload = json.loads(data)

    if isinstance(payload, str):
        data = payload.strip()
        if data.startswith('{'):
            payload = json.loads(data)

    return payload


def main(args=None):
    rclpy.init(args=args)
    node = ServerRequestNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
