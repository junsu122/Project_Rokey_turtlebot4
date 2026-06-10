#!/usr/bin/env python3
"""일반/시각장애인 안내 시나리오를 총괄하는 상태 머신."""

from __future__ import annotations

import json
import math
from collections import deque
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import Bool, Empty, String

from alfred_driving.locations import HOME, LOCATIONS
from alfred_driving.scenario_planner import RoutePlan, build_route_plan, parse_person_request


ROBOT2 = 'robot2'
ROBOT4 = 'robot4'
ROBOTS = (ROBOT2, ROBOT4)


def make_pose_stamped(node: Node, position, rotation) -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = node.get_clock().now().to_msg()
    pose.pose.position.x = float(position[0])
    pose.pose.position.y = float(position[1])
    pose.pose.orientation.z = math.sin(math.radians(rotation) / 2.0)
    pose.pose.orientation.w = math.cos(math.radians(rotation) / 2.0)
    return pose


class ScenarioManagerNode(Node):
    def __init__(self):
        super().__init__('scenario_manager_node')

        self.declare_parameter('patrol_robot', ROBOT2)
        self.patrol_robot = str(self.get_parameter('patrol_robot').value).strip('/')
        if self.patrol_robot not in ROBOTS:
            raise ValueError(f'patrol_robot must be one of {ROBOTS}, got {self.patrol_robot}')

        self.goal_pubs = {
            robot: self.create_publisher(PoseStamped, f'/{robot}/goal_pose_request', 10)
            for robot in ROBOTS
        }
        self.stop_pubs = {
            robot: self.create_publisher(Empty, f'/{robot}/stop_request', 10)
            for robot in ROBOTS
        }
        self.resume_pubs = {
            robot: self.create_publisher(Empty, f'/{robot}/resume_patrol_request', 10)
            for robot in ROBOTS
        }
        self.blind_mode_pub = self.create_publisher(Bool, '/blind_mode', 10)
        self.marker_mode_pubs = {
            robot: self.create_publisher(Bool, f'/{robot}/escort_marker_mode', 10)
            for robot in ROBOTS
        }

        for robot in ROBOTS:
            self.create_subscription(
                String,
                f'/{robot}/nav_status',
                lambda msg, r=robot: self._on_nav_status(msg, r),
                10,
            )
        self.create_subscription(String, '/scenario_request', self._on_scenario_request, 10)

        self.state = 'IDLE'
        self.plan: Optional[RoutePlan] = None
        self.destination_robot: Optional[str] = None
        self.support_robot: Optional[str] = None
        self.arrived = {}
        self.routes = {}
        self.robot_stage = {}
        self.wait_timer = None
        self.patrol_is_stopped = False

        self._set_blind_mode(False)
        self.get_logger().info('scenario_manager_node ready')

    # ------------------------------------------------------------------
    # 시나리오 요청 처리
    # ------------------------------------------------------------------

    def _on_scenario_request(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as err:
            self.get_logger().warn(f'Invalid scenario request: {err}')
            return

        request_type = self._request_type(payload)
        if request_type == 'INTERACTING':
            self._start_interaction(payload)
            return
        if request_type == 'CANCEL':
            self._cancel_scenario(payload)
            return
        if request_type not in ('ESCORT', 'ESCORTING'):
            self.get_logger().warn(f'Unsupported request_type={request_type}. Ignoring request.')
            return

        self._start_escort(payload)

    def _start_interaction(self, payload: dict):
        if self.state == 'IDLE':
            request_robot = str(payload.get('robot_id') or self.patrol_robot).strip('/')
            self.state = 'STOPPING_PATROL'
            self.plan = None
            self.destination_robot = None
            self.support_robot = None
            self.arrived = {}
            self.routes = {}
            self.robot_stage = {}
            self.patrol_is_stopped = False
            self._set_blind_mode(False)
            for robot in ROBOTS:
                self._set_marker_mode(robot, False)
            if request_robot != self.patrol_robot:
                self.state = 'INTERACTING'
                self.get_logger().info(
                    f'INTERACTING request from {request_robot}: no patrol stop needed'
                )
                return
            self.get_logger().info(f'INTERACTING request: stopping {self.patrol_robot} patrol')
            self.stop_pubs[self.patrol_robot].publish(Empty())
            return

        if self.state in ('STOPPING_PATROL', 'INTERACTING'):
            self.get_logger().info('INTERACTING request already active')
            return

        self.get_logger().warn(f'Cannot start INTERACTING while state={self.state}')

    def _start_escort(self, payload: dict):
        if self.state not in ('IDLE', 'STOPPING_PATROL', 'INTERACTING'):
            self.get_logger().warn('Scenario already running. Ignoring ESCORT request.')
            return

        try:
            request = parse_person_request(payload)
            self.plan = build_route_plan(request)
        except (TypeError, ValueError) as err:
            self.get_logger().warn(f'Invalid ESCORT request: {err}')
            return

        self.destination_robot = self.plan.destination_robot
        self.support_robot = ROBOT2 if self.destination_robot == ROBOT4 else ROBOT4
        self.arrived = {}
        self.routes = {}
        self.robot_stage = {}
        self._set_blind_mode(self.plan.request.blind_mode)

        self.get_logger().info(
            f"ESCORT request: person={self.plan.request.person_type} "
            f"blind={self.plan.request.blind_mode} "
            f"destination={self.plan.request.destination_name} "
            f"route={list(self.plan.destination_waypoint_names)}"
        )

        if self.state == 'INTERACTING':
            if self._scenario_uses_patrol_robot() and not self.patrol_is_stopped:
                self.state = 'STOPPING_PATROL'
                self.get_logger().info(
                    f'Stopping {self.patrol_robot} patrol before scenario dispatch'
                )
                self.stop_pubs[self.patrol_robot].publish(Empty())
                return
            self.get_logger().info('Interaction active. Starting escort dispatch.')
            self._start_dispatch()
            return

        if self._can_dispatch_without_stopping_patrol():
            self.get_logger().info('Scenario does not involve patrol robot. Dispatching directly.')
            self._start_dispatch()
            return

        self.state = 'STOPPING_PATROL'
        self.get_logger().info(f'Stopping {self.patrol_robot} patrol before scenario dispatch')
        self.stop_pubs[self.patrol_robot].publish(Empty())

    def _cancel_scenario(self, payload: dict):
        if self.state == 'IDLE':
            self.get_logger().info(
                f"CANCEL request {payload.get('request_id', '?')} ignored: no active scenario"
            )
            return

        self.get_logger().warn(
            f"CANCEL request {payload.get('request_id', '?')} received. "
            "Resetting scenario manager state."
        )
        self.resume_pubs[self.patrol_robot].publish(Empty())
        self._reset()

    # ------------------------------------------------------------------
    # 상태 전이
    # ------------------------------------------------------------------

    def _start_dispatch(self):
        if self.plan is None:
            self._reset()
            return

        if self.plan.same_floor:
            self.state = 'TO_DESTINATION'
            self.routes[self.destination_robot] = self._destination_route(self.destination_robot)
            self._start_route(self.destination_robot)
            return

        self.state = 'TO_TRANSFER'
        self.arrived = {self.destination_robot: False, self.support_robot: False}
        self.robot_stage = {
            self.destination_robot: 'TO_TRANSFER',
            self.support_robot: 'TO_TRANSFER',
        }
        self._send_goal(
            self.support_robot,
            LOCATIONS[self.plan.transfer_origin_name]['pose'],
            escort=True,
        )
        self._send_goal(
            self.destination_robot,
            LOCATIONS[self.plan.transfer_destination_name]['pose'],
            escort=False,
        )
        self.get_logger().info(
            f"Transfer via {self.plan.transfer_kind}: "
            f"{self.support_robot}->{self.plan.transfer_origin_name}, "
            f"{self.destination_robot}->{self.plan.transfer_destination_name}"
        )

    def _finish_transfer_wait(self):
        if self.wait_timer is not None:
            self.wait_timer.cancel()
            self.wait_timer = None
        if self.plan is None:
            self._reset()
            return

        self.state = 'TO_DESTINATION'
        self.routes[self.support_robot] = deque([(HOME[self.support_robot], False)])
        self.routes[self.destination_robot] = self._destination_route(self.destination_robot)
        self._start_route(self.support_robot)
        self._start_route(self.destination_robot)

    # ------------------------------------------------------------------
    # 주행 상태 콜백
    # ------------------------------------------------------------------

    def _on_nav_status(self, msg: String, robot: str):
        if robot == self.patrol_robot and msg.data == 'patrol_stopped' and self.state == 'STOPPING_PATROL':
            self.get_logger().info(f'{self.patrol_robot} patrol stopped')
            self.patrol_is_stopped = True
            if self.plan is None:
                self.state = 'INTERACTING'
                self.get_logger().info('Waiting for ESCORT request')
                return
            self._start_dispatch()
            return

        if msg.data != 'arrived' or self.state == 'IDLE':
            return

        if self.state == 'TO_TRANSFER' and robot in self.arrived:
            self.arrived[robot] = True
            if all(self.arrived.values()):
                self.state = 'TRANSFER_WAIT'
                self.get_logger().info('Both robots reached transfer point')
                self.wait_timer = self.create_timer(3.0, self._finish_transfer_wait)
            return

        if robot in self.routes:
            self._continue_route(robot)

    def _start_route(self, robot: str):
        self.robot_stage[robot] = 'MOVING'
        self._continue_route(robot)

    def _continue_route(self, robot: str):
        route = self.routes.get(robot)
        if route and len(route) > 0:
            name, escort = route.popleft()
            self._send_goal(robot, LOCATIONS[name]['pose'], escort=escort)
            self.get_logger().info(f'{robot} next waypoint: {name}')
            return

        self._mark_done(robot)

    # ------------------------------------------------------------------
    # 로봇 동작 명령
    # ------------------------------------------------------------------

    def _send_goal(self, robot: str, pose, escort: bool):
        self._set_marker_mode(robot, self._marker_enabled_for(escort))
        position, direction = pose
        msg = make_pose_stamped(self, position, direction)
        self.goal_pubs[robot].publish(msg)
        self.get_logger().info(f'Sent goal to {robot}: {position}')

    def _mark_done(self, robot: str):
        self._set_marker_mode(robot, False)
        self.robot_stage[robot] = 'DONE'
        if self.robot_stage and all(stage == 'DONE' for stage in self.robot_stage.values()):
            self.get_logger().info('Scenario complete')
            self.resume_pubs[self.patrol_robot].publish(Empty())
            self._reset()

    # ------------------------------------------------------------------
    # 보조 함수
    # ------------------------------------------------------------------

    def _set_blind_mode(self, enabled: bool):
        msg = Bool()
        msg.data = bool(enabled)
        self.blind_mode_pub.publish(msg)
        self.get_logger().info(f'blind_mode={enabled}')

    def _request_type(self, payload: dict) -> str:
        value = (
            payload.get('request_type')
            or payload.get('requestType')
            or payload.get('mode_type')
        )
        if value:
            return str(value).upper()
        return 'ESCORT' if self._has_destination(payload) else 'INTERACTING'

    def _has_destination(self, payload: dict) -> bool:
        destination = payload.get('destination')
        return bool(
            payload.get('destination_name')
            or payload.get('poi_id')
            or payload.get('goal')
            or (
                isinstance(destination, dict)
                and (destination.get('poi_id') or destination.get('name'))
            )
        )

    def _set_marker_mode(self, robot: str, enabled: bool):
        msg = Bool()
        msg.data = bool(enabled)
        self.marker_mode_pubs[robot].publish(msg)
        self.get_logger().info(f'{robot} escort_marker_mode={enabled}')

    def _marker_enabled_for(self, escort: bool) -> bool:
        return bool(escort and self.plan is not None and self.plan.request.blind_mode)

    def _can_dispatch_without_stopping_patrol(self) -> bool:
        return (
            self.plan is not None
            and self.plan.same_floor
            and self.destination_robot != self.patrol_robot
        )

    def _scenario_uses_patrol_robot(self) -> bool:
        return self.destination_robot == self.patrol_robot or self.support_robot == self.patrol_robot

    def _destination_route(self, robot: str):
        route = [(name, True) for name in self.plan.destination_waypoint_names]
        if robot == ROBOT4 and (not route or route[-1][0] != HOME[ROBOT4]):
            route.append((HOME[ROBOT4], False))
        return deque(route)

    def _reset(self):
        self._set_blind_mode(False)
        for robot in ROBOTS:
            self._set_marker_mode(robot, False)
        self.state = 'IDLE'
        self.plan = None
        self.destination_robot = None
        self.support_robot = None
        self.arrived = {}
        self.routes = {}
        self.robot_stage = {}
        self.patrol_is_stopped = False


def main(args=None):
    rclpy.init(args=args)
    node = ScenarioManagerNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
