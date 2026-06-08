from rclpy.action import ActionClient
from geometry_msgs.msg import Twist
from irobot_create_msgs.msg import AudioNoteVector
from nav2_msgs.action import NavigateToPose
from alfred_vision.audio import SOUND_AMBULANCE, make_audio_msg


class FireHandler:
    def __init__(self, node, ns: str, door_x: float, door_y: float):
        self._node   = node
        self._ns     = ns
        self._door_x = door_x
        self._door_y = door_y
        self._active = False

        self._pub_audio   = node.create_publisher(AudioNoteVector, f'{ns}/cmd_audio', 10)
        self._pub_cmd_vel = node.create_publisher(Twist, f'{ns}/cmd_vel', 10)
        self._nav_client  = ActionClient(node, NavigateToPose, f'{ns}/navigate_to_pose')

    def handle(self, payload: dict):
        if self._active:
            return
        self._active = True

        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        self._node.get_logger().info(f'[{self._ns}] 화재 감지: {cls} (conf={conf})')

        self._pub_cmd_vel.publish(Twist())
        self._node.get_logger().info(f'[{self._ns}] 로봇 정지')

        self._pub_audio.publish(make_audio_msg(SOUND_AMBULANCE))
        self._node.get_logger().info(f'[{self._ns}] 구급차 사이렌 송출')

        if not self._nav_client.wait_for_server(timeout_sec=3.0):
            self._node.get_logger().error(f'[{self._ns}] Nav2 서버 미응답 → 이동 취소')
            self._active = False
            return

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id    = 'map'
        goal.pose.header.stamp       = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x    = self._door_x
        goal.pose.pose.position.y    = self._door_y
        goal.pose.pose.orientation.w = 1.0

        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(self._cb_accepted)
        self._node.get_logger().info(
            f'[{self._ns}] 비상문 이동 요청 (x={self._door_x}, y={self._door_y})'
        )

    def _cb_accepted(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._node.get_logger().error(f'[{self._ns}] Nav2 goal 거부됨')
            self._active = False
            return
        goal_handle.get_result_async().add_done_callback(self._cb_done)

    def _cb_done(self, future):
        self._node.get_logger().info(f'[{self._ns}] 비상문 도착 완료')
        self._active = False
