from geometry_msgs.msg import Twist
from irobot_create_msgs.msg import AudioNoteVector
from alfred_vision.audio import SOUND_AMBULANCE, make_audio_msg


class InjuredHandler:
    def __init__(self, node, ns: str):
        self._node = node
        self._ns   = ns
        self._pub_audio   = node.create_publisher(AudioNoteVector, f'{ns}/cmd_audio', 10)
        self._pub_cmd_vel = node.create_publisher(Twist, f'{ns}/cmd_vel', 10)

    def handle(self, payload: dict):
        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        self._node.get_logger().info(f'[{self._ns}] 부상자 감지: {cls} (conf={conf})')

        self._pub_cmd_vel.publish(Twist())
        self._node.get_logger().info(f'[{self._ns}] 로봇 정지')

        self._pub_audio.publish(make_audio_msg(SOUND_AMBULANCE))
        self._node.get_logger().info(f'[{self._ns}] 구급차 사이렌 송출')
