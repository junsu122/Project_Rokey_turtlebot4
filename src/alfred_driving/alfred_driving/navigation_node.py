#!/usr/bin/env python3

from time import monotonic

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator

from alfred_driving.locations import INITIAL_POSE, LOCATIONS


def namespaced_node(namespace: str, node_name: str) -> str:
    return f'/{namespace.strip("/")}/{node_name}'


def wait_for_dock_status(navigator: TurtleBot4Navigator, timeout_sec: float = 5.0):
    deadline = monotonic() + timeout_sec
    while rclpy.ok() and navigator.is_docked is None and monotonic() < deadline:
        rclpy.spin_once(navigator, timeout_sec=0.1)
    return navigator.is_docked


def wait_until_undocked(navigator: TurtleBot4Navigator, timeout_sec: float = 10.0) -> bool:
    deadline = monotonic() + timeout_sec
    while rclpy.ok() and monotonic() < deadline:
        rclpy.spin_once(navigator, timeout_sec=0.1)
        if navigator.is_docked is False:
            navigator.info('Confirmed undocked.')
            return True
    navigator.warn('Undock confirmation timed out.')
    return False


def wait_until_docked(navigator: TurtleBot4Navigator, timeout_sec: float = 15.0) -> bool:
    deadline = monotonic() + timeout_sec
    while rclpy.ok() and monotonic() < deadline:
        rclpy.spin_once(navigator, timeout_sec=0.1)
        if navigator.is_docked is True:
            navigator.info('Confirmed docked.')
            return True
    navigator.warn('Dock confirmation timed out.')
    return False


def ensure_undocked(navigator: TurtleBot4Navigator) -> None:
    docked = wait_for_dock_status(navigator)
    if docked is None:
        navigator.warn('dock_status not received. Continuing without dock check.')
        return
    if not docked:
        navigator.info('Robot is already undocked.')
        return

    navigator.warn('Robot is docked. Undocking before navigation.')
    navigator.undock()
    wait_until_undocked(navigator)


def same_xy(goal: PoseStamped, location_name: str, tolerance_m: float = 0.05) -> bool:
    position, _direction = LOCATIONS[location_name]['pose']
    return (
        abs(goal.pose.position.x - float(position[0])) <= tolerance_m
        and abs(goal.pose.position.y - float(position[1])) <= tolerance_m
    )


class NavigationNode(Node):
    def __init__(self):
        super().__init__('navigation_node')

        self.declare_parameter('robot_namespace', 'robot4')
        self.robot_namespace = self.get_parameter(
            'robot_namespace'
        ).get_parameter_value().string_value

        self.navigator = TurtleBot4Navigator(namespace=f'/{self.robot_namespace}')

        if self.robot_namespace in INITIAL_POSE:
            position, direction = INITIAL_POSE[self.robot_namespace]
            self.navigator.setInitialPose(self.navigator.getPoseStamped(position, direction))

        topic_name = f'/{self.robot_namespace}/goal_pose_request'

        self.goal_sub = self.create_subscription(
            PoseStamped,
            topic_name,
            self.goal_callback,
            10
        )

        self.is_moving = False

        self.status_pub = self.create_publisher(
            String,
            f'/{self.robot_namespace}/nav_status',
            10
        )

        self.get_logger().info(f"Navigation Node for /{self.robot_namespace}")
        self.get_logger().info(f"Subscribing: {topic_name}")

        self.navigator.waitUntilNav2Active(
            navigator=namespaced_node(self.robot_namespace, 'bt_navigator'),
            localizer=namespaced_node(self.robot_namespace, 'amcl'),
        )
        ensure_undocked(self.navigator)
        self.get_logger().info("Nav2 Active")

    def goal_callback(self, msg):
        if self.is_moving:
            self.get_logger().warn("Robot is already moving. New goal ignored.")
            return

        self.is_moving = True
        self.get_logger().info(f"/{self.robot_namespace} received new goal")

        try:
            ensure_undocked(self.navigator)
            self.navigator.startToPose(msg)

            while not self.navigator.isTaskComplete():
                rclpy.spin_once(self.navigator, timeout_sec=0.1)

            self.get_logger().info(f"/{self.robot_namespace} goal reached")
            if self.robot_namespace == 'robot4' and same_xy(msg, 'station2'):
                self.get_logger().info('/robot4 returned to station2. Docking.')
                self.navigator.dock()
                wait_until_docked(self.navigator)

            status_msg = String()
            status_msg.data = 'arrived'
            self.status_pub.publish(status_msg)
        except Exception as err:
            self.get_logger().error(f"goal_callback error: {err}")
        finally:
            self.is_moving = False


def main(args=None):
    rclpy.init(args=args)
    node = NavigationNode()
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
