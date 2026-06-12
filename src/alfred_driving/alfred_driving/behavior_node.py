#!/usr/bin/env python3
"""Compatibility behavior node for unit.launch.py.

The current alfred_driving runtime uses scenario_manager_node, patrol_node, and
navigation_node for robot motion. This node exists so older bringup files that
still start `alfred_driving behavior_node` do not fail at launch time.
"""

import rclpy
from rclpy.node import Node


class BehaviorNode(Node):
    def __init__(self):
        super().__init__('behavior_node')
        self.declare_parameter('robot_id', '')
        robot_id = str(self.get_parameter('robot_id').value)
        self.get_logger().info(
            f'behavior_node compatibility shim started for {robot_id or "unknown robot"}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = BehaviorNode()
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
