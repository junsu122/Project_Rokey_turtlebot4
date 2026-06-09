import math
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from irobot_create_msgs.msg import AudioNoteVector
from alfred_vision.audio import SOUND_POLICE, make_audio_msg, make_silence_msg

_NAV_UPDATE_THRESHOLD = 0.3
_SIREN_INTERVAL_SEC   = 2.5
_TARGET_LOST_SEC      = 10.0


class SuspiciousHandler:
    def __init__(self, node, ns: str):
        self._node        = node
        self._ns          = ns
        self._following   = False
        self._last_goal   = (None, None)
        self._siren_timer = None
        self._watchdog    = None
        self._last_seen   = 0.0

        self._pub_audio  = node.create_publisher(AudioNoteVector, f'{ns}/cmd_audio',       10)
        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',      10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',  10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request', 10)
        self._patrol_stopped = False

        node.create_subscription(String, f'{ns}/nav_status', self._cb_nav_status, 10)

    def handle(self, payload: dict):
        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        loc  = payload.get('location', {})
        x    = loc.get('x')
        y    = loc.get('y')

        self._node.get_logger().info(f'[{self._ns}] 수상한 인물 감지: {cls} (conf={conf})')

        import time
        self._last_seen = time.monotonic()

        if not self._following:
            self._following      = True
            self._patrol_stopped = False
            self._pub_stop.publish(Empty())
            self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청')
            self._siren_timer = self._node.create_timer(_SIREN_INTERVAL_SEC, self._publish_siren)
            self._watchdog    = self._node.create_timer(_TARGET_LOST_SEC,    self._check_lost)
            self._publish_siren()

        if x is not None and y is not None and self._patrol_stopped:
            self._update_goal(x, y)

    def _cb_nav_status(self, msg: String):
        if msg.data.startswith('patrol_stopped') and self._following and not self._patrol_stopped:
            self._patrol_stopped = True
            self._node.get_logger().info(f'[{self._ns}] patrol_stopped 확인 → 추적 시작')

    def _publish_siren(self):
        self._pub_audio.publish(make_audio_msg(SOUND_POLICE))

    def _check_lost(self):
        import time
        if time.monotonic() - self._last_seen < _TARGET_LOST_SEC:
            return

        self._node.get_logger().info(f'[{self._ns}] 타겟 소실 — 사이렌 정지, 복귀')

        if self._siren_timer:
            self._siren_timer.cancel()
            self._siren_timer = None
        if self._watchdog:
            self._watchdog.cancel()
            self._watchdog = None

        self._pub_audio.publish(make_silence_msg())
        self._pub_resume.publish(Empty())
        self._following      = False
        self._patrol_stopped = False
        self._last_goal      = (None, None)
        self._node.get_logger().info(f'[{self._ns}] 사이렌 정지 → 패트롤 재개')

    def _update_goal(self, x: float, y: float):
        lx, ly = self._last_goal
        if lx is not None and math.hypot(x - lx, y - ly) < _NAV_UPDATE_THRESHOLD:
            return
        self._send_goal(x, y)
        self._last_goal = (x, y)
        self._node.get_logger().info(f'[{self._ns}] 추적 goal 갱신 (x={x}, y={y})')

    def _send_goal(self, x: float, y: float):
        goal = PoseStamped()
        goal.header.frame_id = 'map'
        goal.header.stamp    = self._node.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.w = 1.0
        self._pub_goal.publish(goal)
