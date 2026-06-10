import math
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from rclpy.duration import Duration
from rclpy.time import Time

_APPROACH_OFFSET = 0.2


class InjuredHandler:
    def __init__(self, node, ns: str, tf_buffer, has_patrol: bool = True):
        self._node       = node
        self._ns         = ns
        self._tf_buffer  = tf_buffer
        self._active     = False
        self._waiting    = False
        self._at_patient = False  # 환자 위치 도착 후 조치완료 대기 중
        self._has_patrol = has_patrol
        self._target_x   = None
        self._target_y   = None

        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',          10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',     10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request', 10)

        node.create_subscription(String, f'{ns}/nav_status',        self._cb_nav_status,       10)
        node.create_subscription(Empty,  f'{ns}/emergency_resolve', self._cb_emergency_resolve, 10)

    def is_active(self) -> bool:
        return self._active

    def handle(self, payload: dict):
        if self._active:
            return
        self._active     = True
        self._at_patient = False

        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        loc  = payload.get('location', {})
        self._target_x = loc.get('x')
        self._target_y = loc.get('y')

        self._node.get_logger().info(f'[{self._ns}] 부상자 감지: {cls} (conf={conf})')

        if self._has_patrol:
            self._waiting = True
            self._pub_stop.publish(Empty())
            self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청 → patrol_stopped 대기')
        else:
            # 순찰 없는 로봇: 바로 부상자 위치로 이동
            self._waiting = False
            self._node.get_logger().info(f'[{self._ns}] 순찰 없음 → 바로 부상자 위치 이동')
            self._move_to_patient()

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

    def _move_to_patient(self):
        if self._target_x is not None and self._target_y is not None:
            gx, gy = self._compute_approach_goal(self._target_x, self._target_y)
            goal = PoseStamped()
            goal.header.frame_id    = 'map'
            goal.header.stamp       = self._node.get_clock().now().to_msg()
            goal.pose.position.x    = gx
            goal.pose.position.y    = gy
            goal.pose.orientation.w = 1.0
            self._pub_goal.publish(goal)
            self._node.get_logger().info(f'[{self._ns}] 접근 goal 발행 (x={gx:.2f}, y={gy:.2f})')
        else:
            # 위치 없으면 현위치에서 대기
            self._node.get_logger().warn(f'[{self._ns}] 환자 위치 없음 → 현위치 대기')
            self._at_patient = True

    def _cb_nav_status(self, msg: String):
        if self._has_patrol and self._waiting and msg.data.startswith('patrol_stopped'):
            self._waiting = False
            self._node.get_logger().info(f'[{self._ns}] patrol_stopped 확인 → 환자 위치 이동')
            self._move_to_patient()

        elif self._active and not self._waiting and msg.data == 'arrived':
            self._at_patient = True
            self._node.get_logger().info(f'[{self._ns}] 환자 위치 도착 → monitor 조치완료 대기')

    def _cb_emergency_resolve(self, _msg):
        if not self._active:
            return
        self._node.get_logger().info(f'[{self._ns}] 조치완료 수신 → 패트롤 복귀')
        self._pub_resume.publish(Empty())
        self._active     = False
        self._at_patient = False
