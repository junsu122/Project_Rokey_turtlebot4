#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from irobot_create_msgs.action import Dock, Undock

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator

from alfred_driving.locations import LOCATIONS, TRANSFER, HOME


class EscortNode(Node):
    """
    Takes a single 'goal_location' name on /escort_request.

    The person is always wherever robot2 currently is (it patrols floor 1
    and stops on request — Nav2 plans the route from its live pose, no
    "current location" needs to be supplied).

    Goal on floor 1 (robot2's floor): robot2 drives straight to it.
    Goal on floor 2 (robot4's floor): robot2 escorts to the lift while
    robot4 moves to the matching lift point at the same time.
    After both arrive and a 3s handoff wait:
      - robot2 returns to its station and docks
      - robot4 continues to the final goal, then also returns to its own
        station and docks
    """

    def __init__(self):
        super().__init__('escort_node')

        self.navigator = TurtleBot4Navigator()

        self.goal_pubs = {
            'robot2': self.create_publisher(PoseStamped, '/robot2/goal_pose_request', 10),
            'robot4': self.create_publisher(PoseStamped, '/robot4/goal_pose_request', 10),
        }

        self.dock_clients = {
            'robot2': ActionClient(self, Dock, '/robot2/dock'),
            'robot4': ActionClient(self, Dock, '/robot4/dock'),
        }

        self.undock_clients = {
            'robot2': ActionClient(self, Undock, '/robot2/undock'),
            'robot4': ActionClient(self, Undock, '/robot4/undock'),
        }

        for robot in ('robot2', 'robot4'):
            self.create_subscription(
                String, f'/{robot}/nav_status',
                lambda msg, r=robot: self.status_callback(msg, r),
                10
            )

        self.create_subscription(String, '/escort_request', self.request_callback, 10)

        self.state = "IDLE"
        self.escort_robot = None
        self.continue_robot = None
        self.final_goal_pose = None
        self.arrived = {}
        self.escort_stage = None
        self.continue_stage = None
        self.wait_timer = None

        # goal name waiting on robot2 to confirm its patrol has fully
        # stopped before we send it (or robot4) anywhere
        self.pending_request = None

        self.get_logger().info("Escort Node started")
        self.get_logger().info("Send 'goal_location' to /escort_request")

    # ---------- helpers ----------

    def send_goal(self, robot, pose):
        position, direction = pose
        goal = self.navigator.getPoseStamped(position, direction)
        self.goal_pubs[robot].publish(goal)
        self.get_logger().info(f"Sent goal to {robot}: {position}")

    def send_undock_then_goal(self, robot, pose):
        """Undock first in case the robot is still docked from a previous escort, then move."""
        client = self.undock_clients[robot]
        if not client.wait_for_server(timeout_sec=2.0):
            self.get_logger().warn(f"Undock server for {robot} unavailable, sending goal directly")
            self.send_goal(robot, pose)
            return

        self.get_logger().info(f"Requesting {robot} undock before goal")
        future = client.send_goal_async(Undock.Goal())
        future.add_done_callback(lambda f: self._on_undock_response(f, robot, pose))

    def _on_undock_response(self, future, robot, pose):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn(f"{robot} undock rejected (already undocked?), sending goal")
            self.send_goal(robot, pose)
            return
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda f: self._on_undock_done(robot, pose))

    def _on_undock_done(self, robot, pose):
        self.get_logger().info(f"{robot} undocked, heading to goal")
        self.send_goal(robot, pose)

    def send_dock(self, robot):
        client = self.dock_clients[robot]
        if not client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error(f"Dock action server for {robot} not available")
            return
        client.send_goal_async(Dock.Goal())
        self.get_logger().info(f"{robot} docking")

    def reset(self):
        self.state = "IDLE"
        self.escort_robot = None
        self.continue_robot = None
        self.final_goal_pose = None
        self.arrived = {}
        self.escort_stage = None
        self.continue_stage = None

    def try_finish(self):
        if self.escort_stage == "DONE" and self.continue_stage == "DONE":
            self.get_logger().info("Escort complete — both robots docked.")
            self.reset()

    # ---------- callbacks ----------

    def request_callback(self, msg):
        goal_name = msg.data.strip()
        self.get_logger().info(f"Received escort request: '{goal_name}'")

        if goal_name not in LOCATIONS:
            self.get_logger().warn(f"Unknown location '{goal_name}'. "
                                   f"Available: {list(LOCATIONS.keys())}")
            return

        if self.state != "IDLE" or self.pending_request is not None:
            self.get_logger().warn("An escort is already in progress. Try again later.")
            return

        # Don't send robot2 anywhere yet — it needs to finish canceling its
        # patrol task first, otherwise the new goal races the cancel and
        # robot2 loses its connection to Nav2. Wait for its 'patrol_stopped'
        # confirmation (published once run_patrol() actually exits) before
        # sending any goals.
        self.pending_request = goal_name
        self.get_logger().info(
            f"Escort request '{goal_name}' queued — waiting for robot2 to stop patrol..."
        )

    def start_escort(self, goal_name):
        goal = LOCATIONS[goal_name]

        # The person is wherever robot2 is right now (it just stopped its
        # floor-1 patrol there) — Nav2 plans from its live pose, so no
        # current-location lookup is needed.
        if goal["robot"] == "robot2":
            self.send_goal("robot2", goal["pose"])
            self.get_logger().info(f"Same floor: robot2 → {goal_name}")
            return

        transfer_here = TRANSFER[1]
        transfer_there = TRANSFER[goal["floor"]]

        self.escort_robot = "robot2"
        self.continue_robot = goal["robot"]
        self.final_goal_pose = goal["pose"]
        self.arrived = {self.escort_robot: False, self.continue_robot: False}
        self.escort_stage = None
        self.continue_stage = None
        self.state = "TO_TRANSFER"

        # robot2 has just stopped patrol, so it is already undocked. Sending
        # an undock action here can stall before the navigation goal is sent.
        self.send_goal(self.escort_robot, LOCATIONS[transfer_here]["pose"])
        self.send_undock_then_goal(self.continue_robot, LOCATIONS[transfer_there]["pose"])

        self.get_logger().info(
            f"Floor change via lift: "
            f"{self.escort_robot} → {transfer_here}, {self.continue_robot} → {transfer_there}"
        )

    def status_callback(self, msg, robot):
        if robot == 'robot2' and msg.data.startswith('patrol_stopped'):
            goal_name = self.pending_request
            if ':' in msg.data:
                goal_name = msg.data.split(':', 1)[1].strip()

            if goal_name is None:
                self.get_logger().warn(
                    "robot2 stopped patrol, but no escort destination is known."
                )
                return

            if goal_name not in LOCATIONS:
                self.get_logger().warn(f"Unknown patrol stop destination: '{goal_name}'")
                return

            self.pending_request = None
            self.get_logger().info(
                f"robot2 confirmed patrol stopped — starting escort to '{goal_name}'"
            )
            self.start_escort(goal_name)
            return

        if msg.data != 'arrived':
            return

        if self.state == "TO_TRANSFER" and robot in self.arrived:
            self.arrived[robot] = True
            if all(self.arrived.values()):
                self.state = "WAITING"
                self.get_logger().info("Both robots at transfer point. Waiting 3s for handoff...")
                self.wait_timer = self.create_timer(3.0, self.on_wait_complete)

        elif self.state == "RETURNING":
            if robot == self.escort_robot and self.escort_stage == "TO_HOME":
                self.escort_stage = "DONE"
                self.send_dock(self.escort_robot)
                self.try_finish()

            elif robot == self.continue_robot and self.continue_stage == "TO_GOAL":
                self.continue_stage = "TO_HOME"
                home_name = HOME[self.continue_robot]
                self.send_goal(self.continue_robot, LOCATIONS[home_name]["pose"])
                self.get_logger().info(
                    f"{self.continue_robot} reached destination, returning to {home_name}"
                )

            elif robot == self.continue_robot and self.continue_stage == "TO_HOME":
                self.continue_stage = "DONE"
                self.send_dock(self.continue_robot)
                self.try_finish()

    def on_wait_complete(self):
        self.wait_timer.cancel()
        self.wait_timer = None
        self.state = "RETURNING"
        self.escort_stage = "TO_HOME"
        self.continue_stage = "TO_GOAL"

        home_name = HOME[self.escort_robot]
        self.send_goal(self.escort_robot, LOCATIONS[home_name]["pose"])
        self.send_goal(self.continue_robot, self.final_goal_pose)

        self.get_logger().info(
            f"{self.escort_robot} returning to {home_name}, "
            f"{self.continue_robot} continuing to goal"
        )


def main(args=None):
    rclpy.init(args=args)
    node = EscortNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
