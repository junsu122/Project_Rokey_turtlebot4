#!/usr/bin/env python3
"""DockController — dock_status 구독 + Undock 액션 래퍼. '도킹 여부 추적·undock 실행'만 담당한다.

기동 시 도크에 얹혀 있으면 PATROL을 시작하기 전에 먼저 내려와야 한다(절대 규칙 8과
같은 결의 예외 동작 — FMS는 도킹 여부를 모르고 명령하지도 않으므로 전적으로
로봇 쪽 판단이다). state(PATROL 시작 여부) 판단은 core.RobotStateManager의 몫이고,
여긴 현재 도킹 여부를 알려주고 undock 목표를 던진 뒤 성공/실패만 콜백으로 알려준다.
"""
from __future__ import annotations

import logging
from typing import Callable

from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from action_msgs.msg import GoalStatus
from irobot_create_msgs.action import Undock
from irobot_create_msgs.msg import DockStatus


logger = logging.getLogger('robot_sm.dock')

# undock 종료 통지(성공 여부) — 실패해도 재시도는 호출 측 주기 점검이 담당
OnUndockResult = Callable[[bool], None]


class DockController:
    def __init__(self, node: Node, namespace: str, on_undock_result: OnUndockResult) -> None:
        self._on_undock_result = on_undock_result
        self._goal_handle = None
        # None = 아직 dock_status를 한 번도 못 받음 — 섣불리 판단하지 말고 보류
        self.is_docked: bool | None = None

        node.create_subscription(DockStatus, f'{namespace}/dock_status',
                                 self._on_dock_status, qos_profile_sensor_data)
        self._client = ActionClient(node, Undock, f'{namespace}/undock')

    def _on_dock_status(self, msg: DockStatus) -> None:
        self.is_docked = msg.is_docked

    def undock(self) -> bool:
        """undock goal 전송. 이미 진행 중이면 그대로 두고, action 서버 미준비 시 False
        (호출 측이 다음 주기에 재시도)."""
        if self._goal_handle is not None:
            return True
        if not self._client.server_is_ready():
            logger.error('[DOCK] undock action 서버 미준비 — 다음 주기에 재시도')
            return False
        goal_msg = Undock.Goal()
        future = self._client.send_goal_async(goal_msg)
        future.add_done_callback(self._on_goal_response)
        logger.info('[DOCK] undock 요청 전송')
        return True

    # ── 액션 콜백 ─────────────────────────────────────────────────────
    def _on_goal_response(self, future) -> None:
        handle = future.result()
        if not handle.accepted:
            logger.error('[DOCK] undock goal 거부됨')
            self._goal_handle = None
            self._on_undock_result(False)
            return
        self._goal_handle = handle
        handle.get_result_async().add_done_callback(self._on_result_msg)

    def _on_result_msg(self, future) -> None:
        self._goal_handle = None
        try:
            success = future.result().status == GoalStatus.STATUS_SUCCEEDED
        except Exception:
            logger.exception('[DOCK] undock 결과 조회 실패')
            success = False
        logger.info('[DOCK] undock 종료  success=%s', success)
        self._on_undock_result(success)
