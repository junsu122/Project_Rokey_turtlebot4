from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from irobot_create_msgs.msg import AudioNoteVector
from alfred_vision.audio import SOUND_AMBULANCE, make_audio_msg

# poi_table.yaml 기준 비상 탈출구 후보
_EXIT_POSES = {
    # robot2 옵션
    'entrance':  (-8.05,  2.56),
    'entrance2': (-0.991, 2.48),
    # robot4 옵션
    'gate':      (-1.8,   2.0),
    'gate_b':    (-1.3,   2.0),
}


class FireHandler:
    def __init__(self, node, ns: str, exit_poi: str):
        self._node   = node
        self._ns     = ns
        self._active = False

        pose = _EXIT_POSES.get(exit_poi)
        if pose is None:
            node.get_logger().error(
                f'[{ns}] 알 수 없는 emergency_exit: "{exit_poi}". '
                f'선택지: {list(_EXIT_POSES.keys())}'
            )
            pose = (0.0, 0.0)
        self._door_x, self._door_y = pose
        node.get_logger().info(f'[{ns}] 비상문 설정: {exit_poi} (x={self._door_x}, y={self._door_y})')

        self._pub_audio  = node.create_publisher(AudioNoteVector, f'{ns}/cmd_audio',            10)
        self._pub_stop   = node.create_publisher(Empty,       f'{ns}/stop_request',           10)
        self._pub_goal   = node.create_publisher(PoseStamped, f'{ns}/goal_pose_request',      10)
        self._pub_resume = node.create_publisher(Empty,       f'{ns}/resume_patrol_request',  10)
        self._waiting    = False

        node.create_subscription(String, f'{ns}/nav_status', self._cb_nav_status, 10)

    def handle(self, payload: dict):
        if self._active:
            return
        self._active = True

        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        self._node.get_logger().info(f'[{self._ns}] 화재 감지: {cls} (conf={conf})')

        self._waiting = True
        self._pub_stop.publish(Empty())
        self._node.get_logger().info(f'[{self._ns}] 패트롤 정지 요청 → patrol_stopped 대기')

        self._pub_audio.publish(make_audio_msg(SOUND_AMBULANCE))
        self._node.get_logger().info(f'[{self._ns}] 구급차 사이렌 송출')

    def _cb_nav_status(self, msg: String):
        if self._waiting and msg.data.startswith('patrol_stopped'):
            self._waiting = False
            self._node.get_logger().info(f'[{self._ns}] patrol_stopped 확인 → 비상문 이동')
            goal = PoseStamped()
            goal.header.frame_id    = 'map'
            goal.header.stamp       = self._node.get_clock().now().to_msg()
            goal.pose.position.x    = self._door_x
            goal.pose.position.y    = self._door_y
            goal.pose.orientation.w = 1.0
            self._pub_goal.publish(goal)
            self._node.get_logger().info(
                f'[{self._ns}] 비상문 goal 발행 (x={self._door_x}, y={self._door_y})'
            )
        elif self._active and msg.data == 'arrived':
            self._node.get_logger().info(f'[{self._ns}] 비상문 도착 → 패트롤 재개')
            self._pub_resume.publish(Empty())
            self._active = False
