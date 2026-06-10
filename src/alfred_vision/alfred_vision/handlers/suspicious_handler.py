import json
import math
import time
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from rclpy.duration import Duration
from rclpy.time import Time

_NAV_UPDATE_THRESHOLD = 0.3
_TARGET_LOST_SEC      = 30.0
_APPROACH_OFFSET      = 0.2
_SUSPICIOUS_CLASSES   = {'pistol2', 'knife'}


class SuspiciousHandler:
    def __init__(self, node, ns: str, tf_buffer, has_patrol: bool = True):
        self._node        = node
        self._ns          = ns
        self._tf_buffer   = tf_buffer
        self._following   = False
        self._last_goal   = (None, None)
        self._watchdog    = None
        self._last_seen   = 0.0
        self._has_patrol  = has_patrol

        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',          10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',     10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request', 10)
        self._patrol_stopped = False

        node.create_subscription(String, f'{ns}/nav_status',      self._cb_nav_status, 10)
        # Astra 고정 카메라 감지 토픽 — 항상 구독, active 시에만 처리
        node.create_subscription(String, '/astra/detection/info', self._cb_astra,      10)

    def is_active(self) -> bool:
        return self._following

    def handle(self, payload: dict):
        """OAK-D 최초 트리거 — 정지 요청 + watchdog 시작. 추적 중에는 재진입 무시."""
        if self._following:
            return
        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        self._node.get_logger().info(f'[{self._ns}] 수상한 인물 감지: {cls} (conf={conf})')

        self._following  = True
        self._last_seen  = time.monotonic()

        if self._has_patrol:
            self._patrol_stopped = False
            self._pub_stop.publish(Empty())
            self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청 → Astra 추적 대기')
        else:
            # 순찰 없는 로봇(robot4): 바로 Astra 추적 시작
            self._patrol_stopped = True
            self._node.get_logger().info(f'[{self._ns}] 순찰 없음 → 바로 Astra 추적 시작')

        self._watchdog = self._node.create_timer(_TARGET_LOST_SEC, self._check_lost)

    def _cb_astra(self, msg: String):
        """Astra 감지 콜백 — 추적 중일 때만 처리, 수상한 클래스만 필터링."""
        if not self._following:
            return
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if data.get('class') not in _SUSPICIOUS_CLASSES:
            return

        self._last_seen = time.monotonic()

        loc = data.get('location', {})
        x   = loc.get('x')
        y   = loc.get('y')

        # patrol_stopped 전에는 goal 발행 안 함 — 이동 중 goal 충돌 방지
        if x is not None and y is not None and self._patrol_stopped:
            self._update_goal(x, y)

    def _compute_approach_goal(self, tx: float, ty: float):
        try:
            t  = self._tf_buffer.lookup_transform('map', 'base_link', Time(), timeout=Duration(seconds=0.5))
            rx = t.transform.translation.x
            ry = t.transform.translation.y
            dx, dy = tx - rx, ty - ry
            dist = math.hypot(dx, dy)
            if dist <= _APPROACH_OFFSET:
                return tx, ty
            return tx - (dx / dist) * _APPROACH_OFFSET, ty - (dy / dist) * _APPROACH_OFFSET
        except Exception as e:
            self._node.get_logger().warn(f'[{self._ns}] TF offset 계산 실패: {e}')
            return tx, ty

    def _cb_nav_status(self, msg: String):
        if msg.data.startswith('patrol_stopped') and self._following and not self._patrol_stopped:
            self._patrol_stopped = True
            self._node.get_logger().info(f'[{self._ns}] patrol_stopped 확인 → Astra 추적 시작')

    def _check_lost(self):
        if time.monotonic() - self._last_seen < _TARGET_LOST_SEC:
            return

        self._node.get_logger().info(f'[{self._ns}] Astra 타겟 소실 {_TARGET_LOST_SEC}s → 패트롤 재개')

        if self._watchdog:
            self._watchdog.cancel()
            self._watchdog = None

        self._pub_resume.publish(Empty())
        self._following      = False
        self._patrol_stopped = False
        self._last_goal      = (None, None)

    def _update_goal(self, x: float, y: float):
        lx, ly = self._last_goal
        if lx is not None and math.hypot(x - lx, y - ly) < _NAV_UPDATE_THRESHOLD:
            return
        gx, gy = self._compute_approach_goal(x, y)
        self._send_goal(gx, gy)
        self._last_goal = (x, y)
        self._node.get_logger().info(f'[{self._ns}] 추적 goal 갱신 (x={gx:.2f}, y={gy:.2f})')

    def _send_goal(self, x: float, y: float):
        goal = PoseStamped()
        goal.header.frame_id = 'map'
        goal.header.stamp    = self._node.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.w = 1.0
        self._pub_goal.publish(goal)
