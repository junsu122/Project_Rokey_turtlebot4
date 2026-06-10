import json
import math
import time
from enum import Enum
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from rclpy.duration import Duration
from rclpy.time import Time

_STEP_SIZE = 0.5
_LOST_SEC  = 10.0


class _State(Enum):
    IDLE            = 'IDLE'
    FOLLOWING       = 'FOLLOWING'
    WAITING_RESOLVE = 'WAITING_RESOLVE'


class SuspiciousHandler:
    def __init__(self, node, ns: str, tf_buffer, has_patrol: bool = True):
        self._node        = node
        self._ns          = ns
        self._tf_buffer   = tf_buffer
        self._has_patrol  = has_patrol
        self._state       = _State.IDLE
        self._latest_x    = None
        self._latest_y    = None
        self._last_det_t  = 0.0
        self._waiting_stop = False

        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',          10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',     10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request', 10)

        node.create_subscription(String, f'{ns}/nav_status',       self._cb_nav_status,        10)
        node.create_subscription(String, f'{ns}/detection/info',   self._cb_detection,         10)
        node.create_subscription(Empty,  f'{ns}/emergency_resolve', self._cb_emergency_resolve, 10)

    def is_active(self) -> bool:
        return self._state != _State.IDLE

    def handle(self, payload: dict):
        if self._state != _State.IDLE:
            return

        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        loc  = payload.get('location', {})
        x    = loc.get('x')
        y    = loc.get('y')

        self._node.get_logger().info(
            f'[{self._ns}] 수상한 인물 감지: {cls} (conf={conf}), 위치=({x}, {y})')

        self._latest_x   = x
        self._latest_y   = y
        self._last_det_t = time.monotonic()
        self._state      = _State.FOLLOWING

        if self._has_patrol:
            self._waiting_stop = True
            self._pub_stop.publish(Empty())
            self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청')
        else:
            self._step_toward()

    def _cb_detection(self, msg: String):
        if self._state != _State.FOLLOWING:
            return
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if data.get('event_type') != 'SUSPICIOUS_PERSON':
            return

        loc = data.get('location', {})
        x   = loc.get('x')
        y   = loc.get('y')
        if x is None or y is None:
            return

        self._latest_x   = x
        self._latest_y   = y
        self._last_det_t = time.monotonic()

    def _cb_nav_status(self, msg: String):
        if msg.data.startswith('patrol_stopped'):
            if self._waiting_stop and self._state == _State.FOLLOWING:
                self._waiting_stop = False
                self._node.get_logger().info(f'[{self._ns}] patrol_stopped → 추적 시작')
                self._step_toward()
        elif msg.data == 'arrived':
            if self._state == _State.FOLLOWING and not self._waiting_stop:
                self._step_toward()

    def _cb_emergency_resolve(self, _msg):
        if self._state == _State.IDLE:
            return
        self._node.get_logger().info(f'[{self._ns}] emergency_resolve → 패트롤 복귀')
        self._pub_resume.publish(Empty())
        self._reset()

    def _step_toward(self):
        if time.monotonic() - self._last_det_t > _LOST_SEC:
            self._node.get_logger().info(f'[{self._ns}] {_LOST_SEC}s 탐지 없음 → 대기')
            self._state = _State.WAITING_RESOLVE
            return

        if self._latest_x is None or self._latest_y is None:
            self._node.get_logger().warn(f'[{self._ns}] 위치 없음 → 대기')
            self._state = _State.WAITING_RESOLVE
            return

        try:
            t  = self._tf_buffer.lookup_transform(
                'map', 'base_link', Time(), timeout=Duration(seconds=0.5))
            rx = t.transform.translation.x
            ry = t.transform.translation.y
        except Exception as e:
            self._node.get_logger().warn(f'[{self._ns}] TF 조회 실패: {e}')
            return

        dx   = self._latest_x - rx
        dy   = self._latest_y - ry
        dist = math.hypot(dx, dy)

        if dist <= _STEP_SIZE:
            gx, gy = self._latest_x, self._latest_y
        else:
            gx = rx + (dx / dist) * _STEP_SIZE
            gy = ry + (dy / dist) * _STEP_SIZE

        self._send_goal(gx, gy)
        self._node.get_logger().info(
            f'[{self._ns}] 0.5m step → ({gx:.2f}, {gy:.2f}), '
            f'목표=({self._latest_x:.2f}, {self._latest_y:.2f})')

    def _send_goal(self, x: float, y: float):
        goal = PoseStamped()
        goal.header.frame_id    = 'map'
        goal.header.stamp       = self._node.get_clock().now().to_msg()
        goal.pose.position.x    = x
        goal.pose.position.y    = y
        goal.pose.orientation.w = 1.0
        self._pub_goal.publish(goal)

    def _reset(self):
        self._state        = _State.IDLE
        self._latest_x     = None
        self._latest_y     = None
        self._last_det_t   = 0.0
        self._waiting_stop = False
        self._node.get_logger().info(f'[{self._ns}] 수상자 추적 종료')
