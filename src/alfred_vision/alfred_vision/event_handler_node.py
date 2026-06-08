#!/usr/bin/env python3
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from alfred_vision.fire_handler import FireHandler
from alfred_vision.injured_handler import InjuredHandler
from alfred_vision.suspicious_handler import SuspiciousHandler
from alfred_vision.lost_item_handler import LostItemHandler


class EventHandlerNode(Node):
    def __init__(self):
        super().__init__('event_handler')

        self.declare_parameter('namespace', '/robot2')
        self.declare_parameter('emergency_door_x', 0.0)
        self.declare_parameter('emergency_door_y', 0.0)

        ns     = self.get_parameter('namespace').value.strip()
        door_x = self.get_parameter('emergency_door_x').value
        door_y = self.get_parameter('emergency_door_y').value

        self._handlers = {
            'FIRE':              FireHandler(self, ns, door_x, door_y),
            'INJURED_PERSON':    InjuredHandler(self, ns),
            'SUSPICIOUS_PERSON': SuspiciousHandler(self, ns),
            'LOST_ITEM':         LostItemHandler(self, ns),
        }

        self.create_subscription(String, f'{ns}/detection/info', self._cb_event, 10)
        self.get_logger().info(
            f'[{ns}] 이벤트 핸들러 시작 (비상문: x={door_x}, y={door_y})'
        )

    def _cb_event(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON 파싱 실패: {e}')
            return

        event_type = payload.get('event_type')
        handler = self._handlers.get(event_type)
        if handler:
            handler.handle(payload)
        else:
            self.get_logger().warn(f'알 수 없는 이벤트: {event_type}')


def main(args=None):
    rclpy.init(args=args)
    node = EventHandlerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
