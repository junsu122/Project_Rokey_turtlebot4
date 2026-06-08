#!/usr/bin/env python3
"""
Bridges web requests on /information into the same multi-robot relay-escort
sequence escort_node runs — but driven by the web's two-step protocol and
ending with robot2 back on patrol.

/information carries JSON text (std_msgs/String) shaped like:
    {"op": "publish", "topic": "/information",
     "msg": {"request_type": "STOP" | "ESCORT",
             "destination": {"poi_id": "<LOCATIONS key>", "floor": 2}, ...}}

Expected sequence from the web:
  1. STOP    — customer flags the robot down. robot2's patrol is canceled
               immediately (cancel_and_wait, same as escort_node's flow),
               before any destination is known.
  2. ESCORT  — customer picks a destination. destination.poi_id names a
               LOCATIONS entry; the relay starts from wherever robot2 is.

Same floor as robot2: robot2 drives straight there, then home and docks.
Different floor (robot4's): robot2 escorts to the lift while robot4 moves to
the matching lift point; after both arrive and a 3s handoff, robot4 continues
to the destination then docks at station2, and robot2 returns to station,
docks, and resumes patrolling (resume_patrol_request) — ready for the next
customer.
"""

import json

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
from irobot_create_msgs.action import Dock, Undock

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator

from alfred_driving.locations import LOCATIONS, TRANSFER, HOME


class WebRequestNode(Node):
    """STOP interrupts robot2's patrol; the following ESCORT then runs the
    relay to destination.poi_id and hands robot2 back to patrol when done."""

    def __init__(self):
        super().__init__('web_request_node')

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

        self.stop_pub = self.create_publisher(Empty, '/robot2/stop_request', 10)
        self.resume_patrol_pub = self.create_publisher(Empty, '/robot2/resume_patrol_request', 10)

        for robot in ('robot2', 'robot4'):
            self.create_subscription(
                String, f'/{robot}/nav_status',
                lambda msg, r=robot: self.status_callback(msg, r),
                10
            )

        self.create_subscription(String, '/information', self.information_callback, 10)

        # IDLE -> STOPPING -> AWAITING_DESTINATION -> (TO_TRANSFER -> WAITING ->) RETURNING -> IDLE
        self.state = "IDLE"
        self.escort_robot = None
        self.continue_robot = None
        self.final_goal_pose = None
        self.arrived = {}
        self.escort_stage = None
        self.continue_stage = None
        self.wait_timer = None

        self.get_logger().info("Web Request Node started")
        self.get_logger().info("Listening for web STOP/ESCORT requests on /information")

    # ---------- nav helpers (same approach as escort_node) ----------

    def send_goal(self, robot, pose):
        position, direction = pose
        goal = self.navigator.getPoseStamped(position, direction)
        self.goal_pubs[robot].publish(goal)
        self.get_logger().info(f"Sent goal to {robot}: {position}")

    def send_undock_then_goal(self, robot, pose):
        """Undock first in case the robot is still docked from a previous relay, then move."""
        client = self.undock_clients[robot]
        if not client.wait_for_server(timeout_sec=2.0):
            self.get_logger().warn(f"Undock server for {robot} unavailable, sending goal directly")
            self.send_goal(robot, pose)
            return

        self.get_logger().info(f"Requesting {robot} undock before goal")
        future = client.send_goal_async(Undock.Goal())
        future.add_done_callback(lambda f: self._on_undock_response(f, robot, pose))

    def _on_undock_response(self, future, robot, pose):
        try:
            goal_handle = future.result()
        except Exception as err:
            self.get_logger().warn(f"{robot} undock request failed: {err}. Sending goal directly")
            self.send_goal(robot, pose)
            return

        if not goal_handle.accepted:
            self.get_logger().warn(f"{robot} undock rejected (already undocked?), sending goal")
            self.send_goal(robot, pose)
            return
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda f: self._on_undock_done(robot, pose))

    def _on_undock_done(self, robot, pose):
        self.get_logger().info(f"{robot} undocked, heading to goal")
        self.send_goal(robot, pose)

    def send_dock(self, robot, on_done):
        """Dock and only call on_done() once the action reports it actually finished —
        resume_patrol_request must not fire (and patrol_node must not undock) while
        robot2 is still mid-docking."""
        client = self.dock_clients[robot]
        if not client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error(f"Dock action server for {robot} not available")
            on_done()
            return

        self.get_logger().info(f"{robot} docking")
        future = client.send_goal_async(Dock.Goal())
        future.add_done_callback(lambda f: self._on_dock_response(f, robot, on_done))

    def _on_dock_response(self, future, robot, on_done):
        try:
            goal_handle = future.result()
        except Exception as err:
            self.get_logger().warn(f"{robot} dock request failed: {err}")
            on_done()
            return

        if not goal_handle.accepted:
            self.get_logger().warn(f"{robot} dock goal rejected")
            on_done()
            return
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda f: self._on_dock_done(robot, on_done))

    def _on_dock_done(self, robot, on_done):
        self.get_logger().info(f"{robot} docking complete")
        on_done()

    def mark_docked_and_try_finish(self, robot):
        if robot == self.escort_robot:
            self.escort_stage = "DONE"
        elif robot == self.continue_robot:
            self.continue_stage = "DONE"
        self.try_finish()

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
            self.get_logger().info("Relay complete — both robots docked. Sending robot2 back to patrol.")
            self.resume_patrol_pub.publish(Empty())
            self.reset()

    # ---------- /information handling ----------

    def information_callback(self, msg):
        try:
            envelope = json.loads(msg.data)
        except (TypeError, ValueError) as err:
            self.get_logger().warn(f"Ignoring non-JSON /information message: {err}")
            return

        payload = envelope.get('msg', envelope)
        request_type = payload.get('request_type')

        if request_type in ('STOP', 'INTERACTING'):
            self.handle_stop(payload)
        elif request_type == 'ESCORT':
            self.handle_escort(payload)
        else:
            self.get_logger().warn(f"Ignoring /information with unknown request_type: '{request_type}'")

    def handle_stop(self, payload):
        if self.state != "IDLE":
            self.get_logger().warn("STOP received but a relay is already in progress. Ignoring.")
            return

        self.get_logger().info(
            f"STOP request {payload.get('request_id', '?')} received — interrupting robot2's patrol"
        )
        self.state = "STOPPING"
        self.stop_pub.publish(Empty())

    def handle_escort(self, payload):
        if self.state != "AWAITING_DESTINATION":
            self.get_logger().warn(
                "ESCORT received but robot2 hasn't confirmed a patrol stop yet "
                "(send STOP first). Ignoring."
            )
            return

        poi_id = payload.get('destination', {}).get('poi_id')
        if poi_id not in LOCATIONS:
            self.get_logger().warn(f"Unknown destination poi_id '{poi_id}'. "
                                   f"Available: {list(LOCATIONS.keys())}")
            return

        self.get_logger().info(
            f"ESCORT request {payload.get('request_id', '?')} received — destination '{poi_id}'"
        )
        self.start_relay(poi_id)

    def start_relay(self, goal_name):
        goal = LOCATIONS[goal_name]

        # The person is wherever robot2 is right now (it just stopped on
        # request) — Nav2 plans from its live pose, no current-location
        # lookup needed.
        if goal["robot"] == "robot2":
            self.escort_robot = "robot2"
            self.continue_robot = None
            self.escort_stage = "TO_GOAL"
            self.continue_stage = "DONE"
            self.state = "RETURNING"
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

        # robot2 just stopped patrol, so it is already undocked.
        self.send_goal(self.escort_robot, LOCATIONS[transfer_here]["pose"])
        self.send_undock_then_goal(self.continue_robot, LOCATIONS[transfer_there]["pose"])

        self.get_logger().info(
            f"Floor change via lift: "
            f"{self.escort_robot} → {transfer_here}, {self.continue_robot} → {transfer_there}"
        )

    # ---------- nav status ----------

    def status_callback(self, msg, robot):
        if robot == 'robot2' and msg.data == 'patrol_stopped':
            if self.state != "STOPPING":
                return
            self.state = "AWAITING_DESTINATION"
            self.get_logger().info("robot2 confirmed patrol stopped — waiting for destination")
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
            if robot == self.escort_robot and self.escort_stage == "TO_GOAL":
                # Same-floor case: robot2 reached the destination directly — send it home.
                self.escort_stage = "TO_HOME"
                home_name = HOME[self.escort_robot]
                self.send_goal(self.escort_robot, LOCATIONS[home_name]["pose"])
                self.get_logger().info(f"robot2 reached destination, returning to {home_name}")

            elif robot == self.escort_robot and self.escort_stage == "TO_HOME":
                self.send_dock(
                    self.escort_robot,
                    lambda r=self.escort_robot: self.mark_docked_and_try_finish(r)
                )

            elif robot == self.continue_robot and self.continue_stage == "TO_GOAL":
                self.continue_stage = "TO_HOME"
                home_name = HOME[self.continue_robot]
                self.send_goal(self.continue_robot, LOCATIONS[home_name]["pose"])
                self.get_logger().info(
                    f"{self.continue_robot} reached destination, returning to {home_name}"
                )

            elif robot == self.continue_robot and self.continue_stage == "TO_HOME":
                self.send_dock(
                    self.continue_robot,
                    lambda r=self.continue_robot: self.mark_docked_and_try_finish(r)
                )

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
    node = WebRequestNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
