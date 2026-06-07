#!/usr/bin/env python3
"""Localizer — map 좌표계 기준 로봇의 '현재 위치'를 TF에서 읽어온다.

Nav2 액션 feedback의 current_pose는 '주행 목표가 진행 중'일 때만 온다 — PATROL
중이거나 task 사이 대기 중처럼 보낸 목표가 없으면 갱신되지 않는다. 로봇의
"지금 어디에 있는가"는 본래 localization(AMCL/SLAM)이 항상 내보내는
map → base_link TF가 출처이므로, 이 클래스가 그 TF를 주기적으로 읽어
(x, y, theta)로 변환해 돌려준다. 주행 실행은 navigator.Navigator의 몫이고,
여긴 '위치 추적'만 담당한다.
"""
from __future__ import annotations

import math

from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import (
    Buffer, TransformListener,
    LookupException, ConnectivityException, ExtrapolationException,
)


class Localizer:
    def __init__(self, node: Node, map_frame: str = 'map', base_frame: str = 'base_link') -> None:
        self._node = node
        self._map_frame = map_frame
        self._base_frame = base_frame
        self._buffer = Buffer()
        self._listener = TransformListener(self._buffer, node)

    def current_pose(self) -> dict | None:
        """map → base_link TF를 (x, y, theta) dict로 반환. 아직 TF가 없으면 None.

        기동 직후처럼 localization이 아직 첫 TF를 못 냈을 때 LookupException 등이
        나는 건 정상이므로 조용히 None을 돌려준다(호출 쪽이 이전 값을 유지).
        """
        try:
            tf = self._buffer.lookup_transform(self._map_frame, self._base_frame, Time())
        except (LookupException, ConnectivityException, ExtrapolationException):
            return None
        t = tf.transform.translation
        return {'x': t.x, 'y': t.y, 'theta': _yaw_from_quaternion(tf.transform.rotation)}


def _yaw_from_quaternion(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
