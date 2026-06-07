#!/usr/bin/env python3
"""FakeRobot — RobotStateManager(core.RobotStateManager)가 기대하는 ROS2
인터페이스(Nav2/TF/도킹)를 실로봇·시뮬레이터 없이 흉내 내는 테스트 전용 노드.

RobotStateManager가 실제로 구독·호출하는 것(core.py 기준) 네 가지만 흉내 내면
RobotStateManager는 실로봇과 구분하지 못하고 그대로 PATROL을 시작하고 FMS
task를 수행한다 — MQTT(IF-02/03/ack)는 RobotStateManager가 직접 처리하므로
(별도 브리지 없음, mock_robot.py와 다른 점) 이 노드는 ROS2 쪽만 책임진다:
  ① map→base_link TF                            (Localizer → pose 보고)
  ② {ns}/amcl·bt_navigator get_state + amcl_pose  (Nav2Readiness → 주행 가능 판단)
  ③ {ns}/navigate_to_pose 액션 서버               (Navigator → task/PATROL 주행 실행)
  ④ {ns}/dock_status 토픽                         (DockController → 도킹 여부)

실행 (둘 다 띄워야 동작):
  ros2 run alfred_bridge fake_robot --robot-id robot2
  ros2 run alfred_bridge robot2_state_manager
"""
from __future__ import annotations

import argparse
import math
import sys
import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy,
    qos_profile_sensor_data,
)
from geometry_msgs.msg import PoseWithCovarianceStamped, TransformStamped
from irobot_create_msgs.msg import DockStatus
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from tf2_ros import TransformBroadcaster


# navigator.Nav2Readiness가 구독하는 amcl_pose와 동일 QoS — TRANSIENT_LOCAL이라
# RobotStateManager가 늦게 떠도 마지막 1개를 받아 'initial pose 수신'으로 인지한다.
_AMCL_POSE_QOS = QoSProfile(
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

_TF_PERIOD_SEC = 0.05      # 20Hz — Localizer가 항상 '최근' map→base_link TF를 찾도록
_DOCK_PERIOD_SEC = 1.0
_NAV_STEP_SEC = 0.1        # 주행 시뮬레이션 보간 간격
_MIN_GOAL_DURATION_SEC = 1.0


def _yaw_to_quat(theta: float) -> tuple[float, float]:
    return math.sin(theta / 2.0), math.cos(theta / 2.0)


def _quat_to_yaw(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def _angle_diff(a: float, b: float) -> float:
    """a→b로 가는 최단 각도 차(-pi, pi] — 헤딩을 부드럽게 보간하기 위함."""
    return (b - a + math.pi) % (2.0 * math.pi) - math.pi


class FakeRobot(Node):
    """robot_id 하나(namespace 전체)를 흉내 낸다 — robot2/robot4 공용."""

    def __init__(self, robot_id: str, namespace: str,
                 start_pose: tuple[float, float, float] = (0.0, 0.0, 0.0),
                 linear_speed: float = 0.5) -> None:
        # core.RobotStateManager와 똑같은 이유로 똑같은 리매핑이 필요하다 —
        # TransformBroadcaster는 절대경로 /tf, /tf_static에만 발행하므로, 실제
        # 로봇처럼 {namespace}/tf 아래로 보이게 노드 단위로 리매핑한다.
        tf_remap_args = [
            '--ros-args',
            '--remap', f'/tf:={namespace}/tf',
            '--remap', f'/tf_static:={namespace}/tf_static',
        ]
        super().__init__(f'fake_{robot_id}', cli_args=tf_remap_args)
        self._namespace = namespace
        self._speed = max(linear_speed, 0.05)

        self._lock = threading.Lock()
        x, y, theta = start_pose
        self._pose = {'x': x, 'y': y, 'theta': theta}

        # ① map→base_link TF — Localizer가 읽어 IF-02 pose로 즉시 보고
        self._tf_broadcaster = TransformBroadcaster(self)
        self.create_timer(_TF_PERIOD_SEC, self._publish_tf)

        # ② Nav2Readiness가 기다리는 조건: amcl/bt_navigator 'active' + amcl_pose 1회 이상
        self.create_service(GetState, f'{namespace}/amcl/get_state', self._on_get_state)
        self.create_service(GetState, f'{namespace}/bt_navigator/get_state', self._on_get_state)
        self._amcl_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, f'{namespace}/amcl_pose', _AMCL_POSE_QOS)
        self._publish_amcl_pose()  # TRANSIENT_LOCAL 1회 선발행 — 늦게 뜬 쪽도 마지막 값을 받음

        # ③ navigate_to_pose 액션 서버 — task/PATROL 목표를 받아 '주행'을 흉내 낸다.
        #    execute_callback이 time.sleep으로 블로킹하므로 전용 콜백 그룹 +
        #    MultiThreadedExecutor 조합이 필수(아니면 그동안 TF/dock 타이머가 멎는다).
        self._nav_group = ReentrantCallbackGroup()
        self._nav_server = ActionServer(
            self, NavigateToPose, f'{namespace}/navigate_to_pose',
            execute_callback=self._execute_nav,
            cancel_callback=lambda _req: CancelResponse.ACCEPT,
            callback_group=self._nav_group)

        # ④ dock_status — 항상 '도크에 없음'으로 보고해 PATROL이 곧장 시작되게 한다
        #    (DockController.is_docked=False ⇒ undock 불필요 — undock 액션 서버까지
        #    흉내 낼 필요가 없어진다. 도킹 시나리오 테스트가 필요해지면 여기를 확장).
        self._dock_pub = self.create_publisher(
            DockStatus, f'{namespace}/dock_status', qos_profile_sensor_data)
        self.create_timer(_DOCK_PERIOD_SEC, self._publish_dock_status)

        self.get_logger().info(
            f'[fake_{robot_id}] 준비 완료 — {namespace} 흉내 시작 '
            f'(시작 위치=({x:.2f}, {y:.2f}, {theta:.2f}), speed={self._speed:.2f}m/s)')

    # ── ① map→base_link TF ──────────────────────────────────────────────
    def _publish_tf(self) -> None:
        with self._lock:
            pose = dict(self._pose)
        qz, qw = _yaw_to_quat(pose['theta'])
        tf = TransformStamped()
        tf.header.stamp = self.get_clock().now().to_msg()
        tf.header.frame_id = 'map'
        tf.child_frame_id = 'base_link'
        tf.transform.translation.x = pose['x']
        tf.transform.translation.y = pose['y']
        tf.transform.rotation.z = qz
        tf.transform.rotation.w = qw
        self._tf_broadcaster.sendTransform(tf)

    # ── ② Nav2Readiness: amcl/bt_navigator get_state + amcl_pose ─────────
    def _on_get_state(self, _request, response):
        response.current_state.id = State.PRIMARY_STATE_ACTIVE
        response.current_state.label = 'active'
        return response

    def _publish_amcl_pose(self) -> None:
        with self._lock:
            pose = dict(self._pose)
        qz, qw = _yaw_to_quat(pose['theta'])
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = pose['x']
        msg.pose.pose.position.y = pose['y']
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        self._amcl_pose_pub.publish(msg)

    # ── ③ navigate_to_pose: 목표까지 _speed로 '주행'하는 척 선형 보간 ────
    def _execute_nav(self, goal_handle) -> NavigateToPose.Result:
        p = goal_handle.request.pose.pose
        target = {'x': p.position.x, 'y': p.position.y, 'theta': _quat_to_yaw(p.orientation)}
        with self._lock:
            start = dict(self._pose)
        dist = math.hypot(target['x'] - start['x'], target['y'] - start['y'])
        dtheta = _angle_diff(start['theta'], target['theta'])
        duration = max(dist / self._speed, _MIN_GOAL_DURATION_SEC)
        steps = max(int(duration / _NAV_STEP_SEC), 1)

        self.get_logger().info(
            f'[NAV] 목표 수신 → ({target["x"]:.2f}, {target["y"]:.2f})'
            f'  약 {duration:.1f}s 주행 시뮬레이션')
        for i in range(1, steps + 1):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                self.get_logger().info('[NAV] 목표 취소됨')
                return NavigateToPose.Result()
            t = i / steps
            with self._lock:
                self._pose = {
                    'x': start['x'] + (target['x'] - start['x']) * t,
                    'y': start['y'] + (target['y'] - start['y']) * t,
                    'theta': start['theta'] + dtheta * t,
                }
            time.sleep(_NAV_STEP_SEC)

        with self._lock:
            self._pose = dict(target)
        goal_handle.succeed()
        self.get_logger().info(f'[NAV] 도착  ({target["x"]:.2f}, {target["y"]:.2f})')
        return NavigateToPose.Result()

    # ── ④ dock_status: 항상 '도크에 없음' ────────────────────────────────
    def _publish_dock_status(self) -> None:
        msg = DockStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.is_docked = False
        msg.dock_visible = False
        self._dock_pub.publish(msg)


def main(args=None):
    argv = sys.argv[1:] if args is None else args
    parser = argparse.ArgumentParser(
        description='가짜 robot2/robot4 — RobotStateManager 단독 테스트용 ROS2 인터페이스 흉내')
    parser.add_argument('--robot-id', default='robot2', choices=['robot2', 'robot4'],
                        help='흉내 낼 로봇(기본 robot2) — namespace는 /<robot-id>로 고정')
    parser.add_argument('--start-x', type=float, default=0.0, help='시작 x[m]')
    parser.add_argument('--start-y', type=float, default=0.0, help='시작 y[m]')
    parser.add_argument('--start-theta', type=float, default=0.0, help='시작 헤딩[rad]')
    parser.add_argument('--speed', type=float, default=0.5, help='시뮬 주행 속도[m/s]')
    parsed, ros_argv = parser.parse_known_args(argv)

    rclpy.init(args=ros_argv)
    node = FakeRobot(parsed.robot_id, f'/{parsed.robot_id}',
                     start_pose=(parsed.start_x, parsed.start_y, parsed.start_theta),
                     linear_speed=parsed.speed)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
