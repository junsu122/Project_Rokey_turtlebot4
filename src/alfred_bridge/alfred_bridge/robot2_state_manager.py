#!/usr/bin/env python3
"""robot2 State Manager — FMS task(IF-03)만 따르는 상태 머신 실행 진입점.

실행:
  ros2 run alfred_bridge robot2_state_manager
"""
import rclpy
from rclpy.executors import ExternalShutdownException

from alfred_bridge.core import RobotStateManager

# ── robot2 설정 ───────────────────────────────────────────────────────────
ROBOT2_CONFIG = {
    'namespace':       '/robot2',
    # FMS 호스트 PC 주소 — docs/bridge_config.template.yaml의 broker.host와 같은 출처로 맞출 것
    'mqtt_host':       '192.168.0.20',
    'mqtt_port':       1883,
    # FMS(fms_server)·상대 로봇·브리지와 절대 겹치지 않는 고유 client_id
    'mqtt_client_id':  'robot_sm_robot2',
    # TODO: UI 트랙과 합의한 실제 좌표 수신 토픽으로 교체
    'ui_pose_topic':   'ui/robot2/pose',
    'initial_battery': 100,
    # 자율 PATROL 경로 — task 없을 때 이 좌표를 순서대로 순환 주행한다(절대 규칙 8:
    # FMS는 PATROL을 모르고 명령하지도 않는다 — 전적으로 로봇 쪽 설정).
    # 비워두면([])  patrol 주행 없이 가만히 대기만 한다.
    # 1층 맵 기준 좌표 (x, y[m], theta[rad]) — TurtleBot4Directions 기준 deg→rad 변환
    'patrol_waypoints': [
        {'x': -7.0, 'y': 2.7,  'theta': 1.57},   # WEST
        {'x': -7.0, 'y': 1.3,  'theta': 3.14},   # SOUTH
        {'x': -2.7, 'y': 2.12, 'theta': -1.57},  # EAST
        {'x': -2.7, 'y': 3.3,  'theta': 0.0},    # NORTH
    ],
}


def main(args=None):
    rclpy.init(args=args)
    node = RobotStateManager('robot2', ROBOT2_CONFIG)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():   # ExternalShutdownException 시 rclpy가 이미 컨텍스트를 내렸을 수 있음
            rclpy.shutdown()


if __name__ == '__main__':
    main()
