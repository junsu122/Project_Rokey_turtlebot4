#!/usr/bin/env python3
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener
from alfred_vision.handlers.fire_handler import FireHandler
from alfred_vision.handlers.injured_handler import InjuredHandler
from alfred_vision.handlers.suspicious_handler import SuspiciousHandler
from alfred_vision.handlers.lost_item_handler import LostItemHandler


class EventHandlerNode(Node):
    def __init__(self):
        super().__init__('event_handler')

        self.declare_parameter('namespace',       '/robot2')
        self.declare_parameter('emergency_exit',  'entrance')  # entrance | entrance2 | gate | gate_b | esc2
        self.declare_parameter('has_patrol',      True)        # False이면 patrol_stopped 없이 바로 이동

        ns         = self.get_parameter('namespace').value.strip()
        exit_poi   = self.get_parameter('emergency_exit').value
        has_patrol = self.get_parameter('has_patrol').value

        self._tf_buffer   = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._handlers = {
            'FIRE':              FireHandler(self, ns, exit_poi, has_patrol),
            'INJURED_PERSON':    InjuredHandler(self, ns, self._tf_buffer, has_patrol),
            'SUSPICIOUS_PERSON': SuspiciousHandler(self, ns, self._tf_buffer, has_patrol),
            'LOST_ITEM':         LostItemHandler(self, ns),
        }

        self.create_subscription(String, f'{ns}/detection/info', self._cb_event, 10)
        self.get_logger().info(f'[{ns}] 이벤트 핸들러 시작 (비상출구: {exit_poi})')

    def _cb_event(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON 파싱 실패: {e}')
            return

        event_type = payload.get('event_type')
        handler = self._handlers.get(event_type)
        if handler is None:
            self.get_logger().warn(f'알 수 없는 이벤트: {event_type}')
            return

        busy = next((et for et, h in self._handlers.items() if h.is_active()), None)
        if busy is not None:
            self.get_logger().info(f'[{event_type}] 무시 — {busy} 처리 중')
            return

        handler.handle(payload)


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
