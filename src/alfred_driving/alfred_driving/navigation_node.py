#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator

from alfred_driving.locations import HOME, INITIAL_POSE, LOCATIONS


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

        self.create_subscription(
            Empty,
            f'/{self.robot_namespace}/resume_patrol_request',
            self.resume_patrol_callback,
            10
        )

        self.get_logger().info(f"Navigation Node for /{self.robot_namespace}")
        self.get_logger().info(f"Subscribing: {topic_name}")

        self.navigator.waitUntilNav2Active()
        self.get_logger().info("Nav2 Active")

    def resume_patrol_callback(self, _msg):
        if self.is_moving:
            self.get_logger().warn("Resume patrol: robot is moving. Cancelling first.")
            self.navigator.cancelTask()
            while not self.navigator.isTaskComplete():
                rclpy.spin_once(self.navigator, timeout_sec=0.1)
            self.is_moving = False

        home_name = HOME.get(self.robot_namespace)
        if home_name is None:
            self.get_logger().warn(f"No HOME defined for {self.robot_namespace}")
            return

        home_pose_data = LOCATIONS[home_name]['pose']
        position, direction = home_pose_data
        goal = self.navigator.getPoseStamped(position, direction)

        self.get_logger().info(f"/{self.robot_namespace} emergency resolved → returning to {home_name}")
        self.is_moving = True
        self.navigator.startToPose(goal)
        while not self.navigator.isTaskComplete():
            rclpy.spin_once(self.navigator, timeout_sec=0.1)
        self.is_moving = False

        status_msg = String()
        status_msg.data = 'patrol_resumed'
        self.status_pub.publish(status_msg)
        self.get_logger().info(f"/{self.robot_namespace} returned to {home_name} → patrol_resumed")

    def goal_callback(self, msg):
        if self.is_moving:
            self.get_logger().warn("Robot is moving. Cancelling for new goal.")
            self.navigator.cancelTask()
            while not self.navigator.isTaskComplete():
                rclpy.spin_once(self.navigator, timeout_sec=0.1)
            self.is_moving = False

        self.is_moving = True
        self.get_logger().info(f"/{self.robot_namespace} received new goal")

        self.navigator.startToPose(msg)

        while not self.navigator.isTaskComplete():
            rclpy.spin_once(self.navigator, timeout_sec=0.1)

        self.get_logger().info(f"/{self.robot_namespace} goal reached")
        self.is_moving = False

        status_msg = String()
        status_msg.data = 'arrived'
        self.status_pub.publish(status_msg)


def main(args=None):
    rclpy.init(args=args)
    node = NavigationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()