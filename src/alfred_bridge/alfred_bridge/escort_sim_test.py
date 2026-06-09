#!/usr/bin/env python3
"""escort_node 없이 escort_state_bridge_node의 상태 전이를 테스트하는 시뮬레이터.

escort_node가 실제 에스코트 중 내보내는 메시지 순서를 그대로 흉내 낸다:
  /escort_request "lift2"
  → /robot2/nav_status "patrol_stopped:lift2"   (IDLE → TO_TRANSFER)
  → /robot2/nav_status "arrived"
  → /robot4/nav_status "arrived"                 (TO_TRANSFER → WAITING, 3초 후 → RETURNING)
  → /robot2/nav_status "arrived"                 (escort_stage DONE)
  → /robot4/nav_status "arrived"                 (continue_stage TO_HOME)
  → /robot4/nav_status "arrived"                 (continue_stage DONE → IDLE)

실행 (워크스페이스 source 한 터미널에서):
    python3 escort_sim_test.py

같은 머신에서 escort_state_bridge_node + rosbridge_websocket을 띄워두면
/escort_state(및 web client)에서 IDLE → TO_TRANSFER → WAITING → RETURNING → IDLE
순서로 바뀌는 것을 확인할 수 있다.
"""
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


_STEPS = [
    (0.0, '/escort_request',   'lift2'),
    (1.0, '/robot2/nav_status', 'patrol_stopped:lift2'),
    (2.0, '/robot2/nav_status', 'arrived'),
    (1.0, '/robot4/nav_status', 'arrived'),
    (5.0, '/robot2/nav_status', 'arrived'),   # WAITING → (3초 후) RETURNING 까지 대기 후 진행
    (1.0, '/robot4/nav_status', 'arrived'),
    (1.0, '/robot4/nav_status', 'arrived'),
]


def main() -> None:
    rclpy.init()
    node = Node('escort_sim_test')
    pubs = {
        topic: node.create_publisher(String, topic, 10)
        for _, topic, _ in _STEPS
    }

    # discovery가 끝날 때까지 잠깐 대기 — 너무 빨리 publish하면 구독자가 못 받는다
    time.sleep(1.0)

    for delay, topic, data in _STEPS:
        time.sleep(delay)
        pubs[topic].publish(String(data=data))
        node.get_logger().info(f"발행: {topic} <- '{data}'")

    node.get_logger().info("시뮬레이션 끝. /escort_state 가 IDLE까지 돌아왔는지 확인하세요.")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
