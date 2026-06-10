from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String

_EXIT_POSES = {
    'entrance':  (-8.05,  2.56),
    'entrance2': (-0.991, 2.48),
    'gate':      (-1.8,   2.0),
    'gate_b':    (-1.3,   2.0),
}


class FireHandler:
    def __init__(self, node, ns: str, exit_poi: str, has_patrol: bool = True):
        self._node       = node
        self._ns         = ns
        self._active     = False
        self._has_patrol = has_patrol

        pose = _EXIT_POSES.get(exit_poi)
        if pose is None:
            node.get_logger().error(
                f'[{ns}] 알 수 없는 emergency_exit: "{exit_poi}". '
                f'선택지: {list(_EXIT_POSES.keys())}'
            )
            pose = (0.0, 0.0)
        self._door_x, self._door_y = pose
        node.get_logger().info(f'[{ns}] 비상문 설정: {exit_poi} (x={self._door_x}, y={self._door_y})')

        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',          10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',     10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request', 10)
        self._waiting    = False

        node.create_subscription(String, f'{ns}/nav_status', self._cb_nav_status, 10)

    def is_active(self) -> bool:
        return self._active

    def handle(self, payload: dict):
        if self._active:
            return
        self._active = True

        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        self._node.get_logger().info(f'[{self._ns}] 화재 감지: {cls} (conf={conf})')

        if self._has_patrol:
            self._waiting = True
            self._pub_stop.publish(Empty())
            self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청 → patrol_stopped 대기')
        else:
            # 순찰 없는 로봇(robot4): 바로 비상구로 이동
            self._send_exit_goal()

    def _send_exit_goal(self):
        goal = PoseStamped()
        goal.header.frame_id    = 'map'
        goal.header.stamp       = self._node.get_clock().now().to_msg()
        goal.pose.position.x    = self._door_x
        goal.pose.position.y    = self._door_y
        goal.pose.orientation.w = 1.0
        self._pub_goal.publish(goal)
        self._node.get_logger().info(
            f'[{self._ns}] 비상구 goal 발행 (x={self._door_x}, y={self._door_y})'
        )

    def _cb_nav_status(self, msg: String):
        if self._has_patrol and self._waiting and msg.data.startswith('patrol_stopped'):
            self._waiting = False
            self._node.get_logger().info(f'[{self._ns}] patrol_stopped 확인 → 비상구 이동')
            self._send_exit_goal()
        elif self._active and msg.data == 'arrived':
            self._node.get_logger().info(f'[{self._ns}] 비상구 도착 → 귀환 요청')
            self._pub_resume.publish(Empty())
            self._active = False
