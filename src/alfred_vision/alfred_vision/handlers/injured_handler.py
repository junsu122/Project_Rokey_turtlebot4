from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from irobot_create_msgs.msg import AudioNoteVector
from alfred_vision.audio import SOUND_AMBULANCE, make_audio_msg, make_silence_msg

_SIREN_INTERVAL_SEC = 2.5
_STAY_SEC           = 30.0


class InjuredHandler:
    def __init__(self, node, ns: str):
        self._node        = node
        self._ns          = ns
        self._active      = False
        self._siren_timer = None
        self._stay_timer  = None
        self._waiting     = False

        self._pub_audio  = node.create_publisher(AudioNoteVector, f'{ns}/cmd_audio',            10)
        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',             10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',        10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request',    10)

        node.create_subscription(String, f'{ns}/nav_status', self._cb_nav_status, 10)

    def handle(self, payload: dict):
        if self._active:
            return
        self._active  = True
        self._waiting = True

        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        loc  = payload.get('location', {})
        self._target_x = loc.get('x')
        self._target_y = loc.get('y')

        self._node.get_logger().info(f'[{self._ns}] 부상자 감지: {cls} (conf={conf})')

        self._pub_stop.publish(Empty())
        self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청 → patrol_stopped 대기')

        self._siren_timer = self._node.create_timer(_SIREN_INTERVAL_SEC, self._publish_siren)
        self._publish_siren()

    def _publish_siren(self):
        self._pub_audio.publish(make_audio_msg(SOUND_AMBULANCE))

    def _cb_nav_status(self, msg: String):
        if self._waiting and msg.data.startswith('patrol_stopped'):
            self._waiting = False
            self._node.get_logger().info(f'[{self._ns}] patrol_stopped 확인 → 환자 위치 이동')
            if self._target_x is not None and self._target_y is not None:
                goal = PoseStamped()
                goal.header.frame_id    = 'map'
                goal.header.stamp       = self._node.get_clock().now().to_msg()
                goal.pose.position.x    = self._target_x
                goal.pose.position.y    = self._target_y
                goal.pose.orientation.w = 1.0
                self._pub_goal.publish(goal)
            else:
                self._node.get_logger().warn(f'[{self._ns}] 환자 위치 없음 → 30초 대기 후 복귀')
                self._start_stay_timer()

        elif self._active and not self._waiting and msg.data == 'arrived':
            self._node.get_logger().info(f'[{self._ns}] 환자 위치 도착 → {_STAY_SEC:.0f}초 대기')
            self._start_stay_timer()

    def _start_stay_timer(self):
        if self._stay_timer is None:
            self._stay_timer = self._node.create_timer(_STAY_SEC, self._end_event)

    def _end_event(self):
        if self._siren_timer:
            self._siren_timer.cancel()
            self._siren_timer = None
        if self._stay_timer:
            self._stay_timer.cancel()
            self._stay_timer = None

        self._pub_audio.publish(make_silence_msg())
        self._pub_resume.publish(Empty())
        self._active = False
        self._node.get_logger().info(f'[{self._ns}] 사이렌 종료 → 패트롤 재개')
