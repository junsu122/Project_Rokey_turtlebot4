#!/usr/bin/env python3
"""Navigator — Nav2 NavigateToPose 액션 래퍼. '주행 실행'만 담당한다.

상태(state/task_status) 판단은 하지 않는다 — 그건 core.RobotStateManager의
몫이다. 여긴 목표를 던지고 성공/실패만 콜백으로 알려준다. 로봇의 '현재 위치'는
주행 여부와 무관하게 항상 필요하므로 (Nav2 feedback이 아니라) localization.Localizer가
map→base_link TF에서 직접 읽어 담당한다 — 역할을 명확히 분리했다.
"""
from __future__ import annotations

import logging
import math
from typing import Callable

from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import (
    QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy,
)
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose


logger = logging.getLogger('robot_sm.nav')

# 목표 도착 여부(성공/실패) 통지
OnResult = Callable[[bool], None]

# nav2_simple_commander의 amcl_pose 구독과 동일 QoS — initial pose는 AMCL이
# TRANSIENT_LOCAL로 한 번만 내보낼 수 있어 늦게 구독해도 마지막 값을 받아야 한다.
_AMCL_POSE_QOS = QoSProfile(
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)


class Nav2Readiness:
    """Nav2(amcl·bt_navigator)가 goal을 받을 준비가 됐는지 논블로킹으로 추적한다.

    nav2_simple_commander.BasicNavigator.waitUntilNav2Active와 같은 조건
    (① localizer(amcl)가 active ② initial pose 수신 ③ navigator(bt_navigator)가
    active)을 확인해야 한다 — 그런데 그 함수는 spin_until_future_complete로
    멈춰서 기다리는 방식이라, rclpy.spin(node)로 여러 콜백을 동시에 처리하는
    이 노드 구조에는 그대로 못 쓴다. 또한 action 서버는 bt_navigator가 아직
    inactive(= goal을 받을 준비가 안 된 상태)일 때도 미리 만들어져 있어
    server_is_ready()만으로는 '진짜 준비됐는지' 알 수 없다 — 그 상태로 goal을
    보내면 매번 명시적으로 거부당한다("[NAV] goal 거부됨"의 원인). 여기선
    lifecycle get_state를 주기적으로 비동기 호출해 결과만 캐싱해 둔다.
    """

    def __init__(self, node: Node, namespace: str,
                 navigator: str = 'bt_navigator', localizer: str = 'amcl') -> None:
        self._navigator_active = False
        self._localizer_active = False
        self._initial_pose_received = False
        self._navigator_pending = False
        self._localizer_pending = False
        self._navigator_client = node.create_client(GetState, f'{namespace}/{navigator}/get_state')
        self._localizer_client = node.create_client(GetState, f'{namespace}/{localizer}/get_state')
        node.create_subscription(PoseWithCovarianceStamped, f'{namespace}/amcl_pose',
                                 self._on_amcl_pose, _AMCL_POSE_QOS)

    @property
    def is_ready(self) -> bool:
        return (self._localizer_active and self._initial_pose_received
                and self._navigator_active)

    def check(self) -> None:
        """이미 확인된 항목은 다시 묻지 않는다 — send_goal에서 매번 불러도 무방."""
        if (not self._localizer_active and not self._localizer_pending
                and self._localizer_client.service_is_ready()):
            self._localizer_pending = True
            self._localizer_client.call_async(GetState.Request()) \
                .add_done_callback(self._on_localizer_state)
        if (not self._navigator_active and not self._navigator_pending
                and self._navigator_client.service_is_ready()):
            self._navigator_pending = True
            self._navigator_client.call_async(GetState.Request()) \
                .add_done_callback(self._on_navigator_state)

    def _on_amcl_pose(self, _msg: PoseWithCovarianceStamped) -> None:
        if not self._initial_pose_received:
            self._initial_pose_received = True
            logger.info('[NAV] initial pose 수신')

    def _on_localizer_state(self, future) -> None:
        self._localizer_pending = False
        if _lifecycle_state_label(future) == 'active':
            self._localizer_active = True
            logger.info('[NAV] amcl active')

    def _on_navigator_state(self, future) -> None:
        self._navigator_pending = False
        if _lifecycle_state_label(future) == 'active':
            self._navigator_active = True
            logger.info('[NAV] bt_navigator active')


def _lifecycle_state_label(future) -> str | None:
    try:
        return future.result().current_state.label
    except Exception:
        return None


class Navigator:
    def __init__(self, node: Node, namespace: str, on_result: OnResult,
                 ready: Nav2Readiness) -> None:
        self._node = node
        self._on_result = on_result
        self._ready = ready
        self._goal_handle = None
        self._client = ActionClient(node, NavigateToPose, f'{namespace}/navigate_to_pose')

    def send_goal(self, x: float, y: float, theta: float = 0.0, frame: str = 'map') -> bool:
        """목표 전송. Nav2 미준비/액션 서버 미준비 시 False(core가 재시도하거나
        task FAILED로 처리)."""
        self._ready.check()
        if not self._ready.is_ready:
            logger.error('[NAV] Nav2 미준비(amcl/bt_navigator) — goal 전송 보류')
            return False
        if not self._client.server_is_ready():
            logger.error('[NAV] action 서버 미준비 — goal 전송 불가')
            return False
        self.cancel()
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = _make_pose(x, y, theta, frame)
        future = self._client.send_goal_async(goal_msg)
        future.add_done_callback(self._on_goal_response)
        logger.info('[NAV] goal 전송  (%.2f, %.2f, theta=%.2f)', x, y, theta)
        return True

    def cancel(self) -> None:
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None

    # ── 액션 콜백 ─────────────────────────────────────────────────────
    def _on_goal_response(self, future) -> None:
        handle = future.result()
        if not handle.accepted:
            logger.error('[NAV] goal 거부됨')
            self._goal_handle = None
            self._on_result(False)
            return
        self._goal_handle = handle
        handle.get_result_async().add_done_callback(self._on_result_msg)

    def _on_result_msg(self, future) -> None:
        self._goal_handle = None
        try:
            success = future.result().status == GoalStatus.STATUS_SUCCEEDED
        except Exception:
            logger.exception('[NAV] 결과 조회 실패')
            success = False
        logger.info('[NAV] 목표 종료  success=%s', success)
        self._on_result(success)


def _make_pose(x: float, y: float, theta: float, frame: str) -> PoseStamped:
    p = PoseStamped()
    p.header.frame_id = frame
    p.pose.position.x = x
    p.pose.position.y = y
    p.pose.orientation.z = math.sin(theta / 2.0)
    p.pose.orientation.w = math.cos(theta / 2.0)
    return p
