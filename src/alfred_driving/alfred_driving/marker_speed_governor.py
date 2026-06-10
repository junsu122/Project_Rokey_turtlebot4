"""marker_speed_governor — ArUco 마커 크기/거리로 Nav2 속도 상한을 조절한다.

goal 은 RViz 'Nav2 Goal' 로 직접 주면 됨. 이 노드는 goal 을 전혀 모르고
오직 속도상한(%)만 계속 발행한다. Nav2 는 cmd_vel 을 100% 자기가 통제 →
가로채기 없음(현실 로봇 불안정 방지).

기본 매핑:
  bbox 작음/마커 안 보임      → lost_pct
  bbox 중간                   → slow_pct ~ max_pct 선형 증가
  bbox 큼(close_area 이상)    → max_pct

tracker 메시지에 bbox가 없으면 distance_m 기반으로 대체 계산한다.

주의: SpeedLimit.speed_limit=0.0 은 '제한 없음(=풀속도)' 이라 정지 용도로 못 씀.
      그래서 lost_pct/min_pct 는 항상 0 보다 큰 값.
"""
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
from nav2_msgs.msg import SpeedLimit


class MarkerSpeedGovernor(Node):
    """ArUco 사용자 마커 정보를 Nav2 SpeedLimit 토픽으로 변환하는 노드.

    이 노드는 goal을 보내거나 cmd_vel을 직접 제어하지 않는다. 오직 Nav2가
    참고할 속도 상한(`/robotX/speed_limit`)만 주기적으로 발행한다.
    """

    def __init__(self):
        """속도 매핑 파라미터, 구독 토픽, SpeedLimit publisher를 초기화한다."""
        super().__init__('marker_speed_governor')

        self.declare_parameter('namespace', 'robot4')
        self.declare_parameter('user_topic', '/aruco_tracker/user')
        self.declare_parameter('enable_topic', '/blind_mode')# 이 속도 제어 켜고 끄는 토픽
        self.declare_parameter('enabled', False) # 속도 제어 할 지 안할지
        self.declare_parameter('use_bbox_area', True) # bbox 면적기반 계산 우선 사용할 지(박스 or 거리)
        self.declare_parameter('far_stop_area_ratio', 0.005) # bbox 충분히 작을 때 기준,39px
        self.declare_parameter('close_fast_area_ratio', 0.070) # bbox 충분히 클 때 기준 147px
        self.declare_parameter('slow_pct', 35.0)     #  bbox 중간 구간 시작 속도
        self.declare_parameter('lost_pct', 1.0)      # 마커 분실 시 속도(정지)
        self.declare_parameter('near_dist', 0.4)     # 이 거리 이하 = max_pct
        self.declare_parameter('far_dist', 1.5)      # 이 거리 이상 = min_pct
        self.declare_parameter('min_pct', 10.0)      # 멀 때/분실 시 최저 속도(%)
        self.declare_parameter('max_pct', 100.0)     # 가까울 때 속도(%)
        self.declare_parameter('lost_timeout', 0.8)  # 이 시간 이상 미검출 = 최저속도
        self.declare_parameter('rate_hz', 10.0) # 속도 제한 발행 주기

        ns = self.get_parameter('namespace').value
        self._user_topic = self.get_parameter('user_topic').value
        self._enable_topic = str(self.get_parameter('enable_topic').value)
        self._enabled = bool(self.get_parameter('enabled').value)
        self._use_bbox_area = bool(self.get_parameter('use_bbox_area').value)
        self._far_area = float(self.get_parameter('far_stop_area_ratio').value)
        self._close_area = float(self.get_parameter('close_fast_area_ratio').value)
        self._slow_pct = max(1.0, float(self.get_parameter('slow_pct').value))
        self._lost_pct = max(1.0, float(self.get_parameter('lost_pct').value))
        self._near = float(self.get_parameter('near_dist').value)
        self._far = float(self.get_parameter('far_dist').value)
        self._min_pct = max(1.0, float(self.get_parameter('min_pct').value))  # 0 금지
        self._max_pct = float(self.get_parameter('max_pct').value)
        self._lost_timeout = float(self.get_parameter('lost_timeout').value)
        rate_hz = float(self.get_parameter('rate_hz').value)

        prefix = f'/{ns.strip("/")}' if ns.strip('/') else ''

        self._last_dist = None
        self._last_area_ratio = None
        self._last_seen = None

        self.create_subscription(String, self._user_topic, self._user_cb, 10)
        self.create_subscription(Bool, self._enable_topic, self._enable_cb, 10)
        self._pub = self.create_publisher(SpeedLimit, f'{prefix}/speed_limit', 10)
        self.create_timer(1.0 / rate_hz, self._tick)

        self.get_logger().info(
            f'marker_speed_governor ready: {self._user_topic} → {prefix}/speed_limit | '
            f'enable_topic={self._enable_topic}, enabled={self._enabled}, '
            f'bbox far={self._far_area:.3f}({self._lost_pct:.0f}%) '
            f'close={self._close_area:.3f}({self._max_pct:.0f}%), '
            f'lost>{self._lost_timeout}s → {self._lost_pct:.0f}%')

    def _user_cb(self, msg: String):
        """`/aruco_tracker/user` 메시지를 받아 마지막 사용자 마커 상태를 저장한다.

        저장하는 값:
        - `_last_dist`: 사용자 마커까지의 거리
        - `_last_area_ratio`: 이미지 전체 대비 bbox 면적 비율
        - `_last_seen`: 마지막으로 사용자 마커를 본 시간

        이 함수는 속도를 바로 발행하지 않고, `_tick()`이 주기적으로 최신 값을 읽어
        speed limit을 계산한다.
        """
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        if data.get('found') and data.get('user'):
            user = data['user']
            try:
                self._last_dist = float(user['distance_m'])
            except (TypeError, ValueError, KeyError):
                self._last_dist = None
            try:
                width = float(user.get('bbox_width_px'))
                height = float(user.get('bbox_height_px'))
                image_width = float(user.get('image_width'))
                image_height = float(user.get('image_height'))
                self._last_area_ratio = (width * height) / (image_width * image_height)
            except (AttributeError, TypeError, ValueError, ZeroDivisionError):
                self._last_area_ratio = None
            self._last_seen = self.get_clock().now()

    def _enable_cb(self, msg: Bool):
        """escort marker mode ON/OFF를 갱신한다.

        scenario_manager_node가 `/robot2/escort_marker_mode` 또는
        `/robot4/escort_marker_mode`를 발행하면 이 callback이 호출된다.
        False이면 ArUco 정보를 무시하고 속도 제한을 100%로 둔다.
        """
        if self._enabled == bool(msg.data):
            return
        self._enabled = bool(msg.data)
        self.get_logger().info(f'blind ArUco speed control enabled={self._enabled}')

    def _visible(self):
        """사용자 마커가 최근 timeout 안에 보였는지 판단한다."""
        if self._last_seen is None:
            return False
        dt = (self.get_clock().now() - self._last_seen).nanoseconds * 1e-9
        return dt <= self._lost_timeout

    def _pct_for_distance(self, d):
        """거리 기반 속도 퍼센트를 계산한다.

        가까울수록 빠르게, 멀수록 느리게 매핑한다.
        - `near_dist` 이하: `max_pct`
        - `far_dist` 이상: `min_pct`
        - 그 사이는 선형 보간
        """
        if d <= self._near:
            return self._max_pct
        if d >= self._far:
            return self._min_pct
        t = (d - self._near) / (self._far - self._near)
        return self._max_pct - (self._max_pct - self._min_pct) * t

    def _pct_for_area(self, area):
        """bbox 면적 비율 기반 속도 퍼센트를 계산한다.

        bbox가 작다는 것은 사용자가 멀거나 마커가 작게 보인다는 뜻이므로 느리게,
        bbox가 크다는 것은 가까이 있다는 뜻이므로 빠르게 이동하도록 매핑한다.
        """
        if area <= self._far_area:
            return self._lost_pct
        if area >= self._close_area:
            return self._max_pct
        span = self._close_area - self._far_area
        t = (area - self._far_area) / span
        return self._slow_pct + (self._max_pct - self._slow_pct) * max(0.0, min(1.0, t))

    def _tick(self):
        """현재 marker mode와 사용자 마커 상태를 바탕으로 SpeedLimit을 발행한다.

        우선순위:
        1. marker mode가 꺼져 있으면 100%
        2. marker가 보이고 bbox 정보가 있으면 bbox 기반 계산
        3. marker가 보이고 거리 정보만 있으면 거리 기반 계산
        4. marker mode는 켜져 있는데 marker가 안 보이면 lost_pct
        """
        if not self._enabled:
            pct = self._max_pct
        elif self._visible() and self._use_bbox_area and self._last_area_ratio is not None:
            pct = self._pct_for_area(self._last_area_ratio)
        elif self._visible() and self._last_dist is not None:
            pct = self._pct_for_distance(self._last_dist)
        else:
            pct = self._lost_pct
        msg = SpeedLimit()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.percentage = True
        msg.speed_limit = float(pct)
        self._pub.publish(msg)
        self.get_logger().info(
            f"dist={'--' if self._last_dist is None else f'{self._last_dist:.2f}m'} "
            f"bbox={'--' if self._last_area_ratio is None else f'{self._last_area_ratio:.3f}'} "
            f"visible={self._visible()} → speed_limit={pct:.0f}%",
            throttle_duration_sec=1.0)


def main():
    """marker_speed_governor 실행 진입점."""
    rclpy.init()
    node = None
    try:
        node = MarkerSpeedGovernor()
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
