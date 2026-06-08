import math
from rclpy.action import ActionClient
from geometry_msgs.msg import Twist
from irobot_create_msgs.msg import AudioNoteVector
from nav2_msgs.action import NavigateToPose
from alfred_vision.audio import SOUND_POLICE, make_audio_msg

_NAV_UPDATE_THRESHOLD = 0.3
_SIREN_INTERVAL_SEC   = 2.5


class SuspiciousHandler:
    def __init__(self, node, ns: str):
        self._node       = node
        self._ns         = ns
        self._following  = False
        self._last_goal  = (None, None)
        self._siren_timer = None

        self._pub_audio   = node.create_publisher(AudioNoteVector, f'{ns}/cmd_audio', 10)
        self._pub_cmd_vel = node.create_publisher(Twist, f'{ns}/cmd_vel', 10)
        self._nav_client  = ActionClient(node, NavigateToPose, f'{ns}/navigate_to_pose')

    def handle(self, payload: dict):
        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        loc  = payload.get('location', {})
        x    = loc.get('x')
        y    = loc.get('y')

        self._node.get_logger().info(f'[{self._ns}] 수상한 인물 감지: {cls} (conf={conf})')

        if not self._following:
            self._following = True
            self._pub_cmd_vel.publish(Twist())
            self._node.get_logger().info(f'[{self._ns}] 로봇 정지')
            self._siren_timer = self._node.create_timer(_SIREN_INTERVAL_SEC, self._publish_siren)
            self._publish_siren()

        if x is not None and y is not None:
            self._update_goal(x, y)

    def _publish_siren(self):
        self._pub_audio.publish(make_audio_msg(SOUND_POLICE))

    def _update_goal(self, x: float, y: float):
        lx, ly = self._last_goal
        if lx is not None and math.hypot(x - lx, y - ly) < _NAV_UPDATE_THRESHOLD:
            return

        if not self._nav_client.wait_for_server(timeout_sec=1.0):
            self._node.get_logger().error(f'[{self._ns}] Nav2 서버 미응답')
            return

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id    = 'map'
        goal.pose.header.stamp       = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x    = x
        goal.pose.pose.position.y    = y
        goal.pose.pose.orientation.w = 1.0

        self._nav_client.send_goal_async(goal)
        self._last_goal = (x, y)
        self._node.get_logger().info(f'[{self._ns}] 추적 goal 갱신 (x={x}, y={y})')
