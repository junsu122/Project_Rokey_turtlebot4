#!/usr/bin/env python3

# Copyright 2023 Clearpath Robotics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @author Hilary Luo (hluo@clearpathrobotics.com)

from math import floor
from threading import Lock, Thread
from time import sleep

import rclpy

from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Empty, String
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator

from alfred_driving.locations import INITIAL_POSE

BATTERY_HIGH = 0.95
BATTERY_LOW = 0.2  # when the robot will go charge
BATTERY_CRITICAL = 0.1  # when the robot will shutdown


class Robot2Monitor(Node):
    """
    Background node for robot2: tracks battery state, listens for stop/escort
    requests (to interrupt the patrol), and — once the patrol stops — relays
    navigation goals from escort_node/web_request_node and reports arrival.
    A 'resume_patrol_request' afterwards hands control back to the patrol loop.

    Everything routes through this single node + the one TurtleBot4Navigator
    created in main(), so robot2 is never controlled by two navigators at
    once (running a separate navigation_node for robot2 alongside this patrol
    causes both to fight over the Nav2 action server).
    """

    def __init__(self, lock):
        super().__init__('battery_monitor', namespace='robot2')

        self.lock = lock
        self.escort_requested = False
        self.escort_goal_name = None
        self.pending_goal = None
        self.battery_percent = None
        self.resume_requested = False

        self.battery_state_subscriber = self.create_subscription(
            BatteryState,
            'battery_state',
            self.battery_state_callback,
            qos_profile_sensor_data)

        self.escort_request_subscriber = self.create_subscription(
            String,
            '/escort_request',
            self.escort_request_callback,
            10)

        # Lets web_request_node interrupt the patrol immediately, before a
        # destination is known (the customer flags the robot down first and
        # picks a destination afterwards) — same effect as escort_request but
        # without forcing a (not yet known) goal name.
        self.stop_request_subscriber = self.create_subscription(
            Empty,
            'stop_request',
            self.stop_request_callback,
            10)

        # Tells a robot2 that has finished an escort relay (docked again) to
        # leave run_escort_goal_executor and resume its floor-1 patrol.
        self.resume_patrol_subscriber = self.create_subscription(
            Empty,
            'resume_patrol_request',
            self.resume_patrol_callback,
            10)

        # Same topic escort_node publishes to — this node now plays the role
        # navigation_node would normally play for robot2.
        self.goal_subscriber = self.create_subscription(
            PoseStamped,
            'goal_pose_request',
            self.goal_callback,
            10)

        self.status_publisher = self.create_publisher(String, 'nav_status', 10)

    # Callbacks
    def battery_state_callback(self, batt_msg: BatteryState):
        with self.lock:
            self.battery_percent = batt_msg.percentage

    def escort_request_callback(self, msg):
        with self.lock:
            self.escort_requested = True
            self.escort_goal_name = msg.data.strip()

    def stop_request_callback(self, _msg):
        with self.lock:
            self.escort_requested = True

    def resume_patrol_callback(self, _msg):
        with self.lock:
            self.resume_requested = True

    def goal_callback(self, msg):
        with self.lock:
            self.pending_goal = msg

    def publish_arrived(self):
        status_msg = String()
        status_msg.data = 'arrived'
        self.status_publisher.publish(status_msg)

    def publish_patrol_stopped(self):
        status_msg = String()
        with self.lock:
            goal_name = self.escort_goal_name
        if goal_name:
            status_msg.data = f'patrol_stopped:{goal_name}'
        else:
            status_msg.data = 'patrol_stopped'
        self.status_publisher.publish(status_msg)

    def thread_function(self):
        executor = SingleThreadedExecutor()
        executor.add_node(self)
        executor.spin()


def cancel_and_wait(navigator):
    """Cancel the active Nav2 goal and wait until Nav2 reports it finished."""
    if navigator.result_future is None or navigator.goal_handle is None:
        return  # no active goal to cancel

    navigator.info('Canceling current task...')
    try:
        cancel_future = navigator.goal_handle.cancel_goal_async()
    except Exception as err:
        navigator.warn(f'Cancel request failed or goal already ended: {err}')
        return

    while not cancel_future.done():
        rclpy.spin_once(navigator, timeout_sec=0.1)

    navigator.info('Cancel accepted. Waiting for patrol task result...')
    while rclpy.ok() and not navigator.isTaskComplete():
        rclpy.spin_once(navigator, timeout_sec=0.1)

    navigator.info('Patrol task fully stopped.')


def run_patrol(navigator, monitor, lock, goal_pose):
    """Patrol loop. Returns True if stopped because an escort was requested."""
    battery_percent = None
    position_index = 0

    while True:
        with lock:
            battery_percent = monitor.battery_percent
            escort_requested = monitor.escort_requested

        if escort_requested:
            navigator.info('Escort request received. Stopping patrol.')
            cancel_and_wait(navigator)
            return True

        if battery_percent is not None:
            navigator.info(f'Battery is at {(battery_percent*100):.2f}% charge')

            # Check battery charge level
            if battery_percent < BATTERY_CRITICAL:
                navigator.error('Battery critically low. Charge or power down')
                return False
            elif battery_percent < BATTERY_LOW:
                # Go near the dock
                navigator.info('Docking for charge')
                navigator.startToPose(navigator.getPoseStamped([-1.0, 1.0],
                                      TurtleBot4Directions.EAST))
                navigator.dock()

                if not navigator.getDockedStatus():
                    navigator.error('Robot failed to dock')
                    return False

                # Wait until charged
                navigator.info('Charging...')
                battery_percent_prev = 0
                while battery_percent < BATTERY_HIGH:
                    sleep(15)
                    battery_percent_prev = floor(battery_percent*100)/100
                    with lock:
                        battery_percent = monitor.battery_percent

                    # Print charge level every time it increases a percent
                    if battery_percent > (battery_percent_prev + 0.01):
                        navigator.info(f'Battery is at {(battery_percent*100):.2f}% charge')

                # Undock
                navigator.undock()
                position_index = 0

            else:
                # Navigate to next position, polling so an escort request can interrupt it
                try:
                    accepted = navigator.goToPose(goal_pose[position_index])
                except Exception as err:
                    navigator.error(f'Failed to send patrol goal: {err}')
                    sleep(1.0)
                    continue

                if not accepted:
                    navigator.error('Nav2 rejected patrol goal.')
                    sleep(1.0)
                    continue

                interrupted = False
                while rclpy.ok() and not navigator.isTaskComplete():
                    with lock:
                        interrupted = monitor.escort_requested
                    if interrupted:
                        navigator.info('Escort request received mid-navigation. Canceling.')
                        cancel_and_wait(navigator)
                        break
                    rclpy.spin_once(navigator, timeout_sec=0.1)

                if interrupted:
                    return True

                position_index = position_index + 1
                if position_index >= len(goal_pose):
                    position_index = 0


def run_escort_goal_executor(navigator, monitor, lock):
    """
    Acts as robot2's navigation_node: waits for goals published by
    escort_node/web_request_node on /robot2/goal_pose_request, drives to
    them, and reports 'arrived' on /robot2/nav_status — all using the single
    navigator that already controls robot2.

    Returns once a 'resume_patrol_request' arrives (the relay finished and
    robot2 is docked again), so main() can hand control back to run_patrol.
    """
    navigator.info('Patrol fully stopped. Confirmed ready — waiting for escort goals.')

    while rclpy.ok():
        with lock:
            goal = monitor.pending_goal
            monitor.pending_goal = None
            resume_requested = monitor.resume_requested

        if resume_requested:
            navigator.info('Resume-patrol request received. Handing back to patrol loop.')
            return True

        if goal is not None:
            navigator.info('Received navigation goal.')
            try:
                accepted = navigator.goToPose(goal)
            except Exception as err:
                navigator.error(f'Failed to send escort goal: {err}')
                continue

            if not accepted:
                navigator.error('Nav2 rejected escort goal.')
                continue

            interrupted = False
            while rclpy.ok() and not navigator.isTaskComplete():
                with lock:
                    resume_requested = monitor.resume_requested

                if resume_requested:
                    navigator.info('Resume requested while escort goal is active. Canceling goal.')
                    cancel_and_wait(navigator)
                    return True

                rclpy.spin_once(navigator, timeout_sec=0.1)

            if interrupted:
                continue

            navigator.info('Goal reached.')
            monitor.publish_arrived()
        else:
            sleep(0.1)

    return False


def main(args=None):
    rclpy.init(args=args)

    lock = Lock()
    monitor = Robot2Monitor(lock)

    navigator = TurtleBot4Navigator(namespace='/robot2')

    thread = Thread(target=monitor.thread_function, daemon=True)
    thread.start()

    # Start on dock
    if not navigator.getDockedStatus():
        navigator.info('Docking before intialising pose')
        navigator.dock()

    # Set initial pose to where robot2 actually starts on the map
    position, direction = INITIAL_POSE['robot2']
    navigator.setInitialPose(navigator.getPoseStamped(position, direction))

    # Wait for Nav2
    navigator.waitUntilNav2Active()

    # Undock
    navigator.undock()

    # Prepare patrol waypoints
    goal_pose = []
    goal_pose.append(navigator.getPoseStamped([-7.0, 2.7], TurtleBot4Directions.EAST))
    goal_pose.append(navigator.getPoseStamped([-7.0, 1.3], TurtleBot4Directions.NORTH))
    goal_pose.append(navigator.getPoseStamped([-2.7, 2.12], TurtleBot4Directions.WEST))
    goal_pose.append(navigator.getPoseStamped([-2.7, 3.3], TurtleBot4Directions.SOUTH))

    while rclpy.ok():
        escort_triggered = run_patrol(navigator, monitor, lock, goal_pose)

        if not escort_triggered:
            navigator.info('Patrol stopped.')
            break

        # Tell escort_node/web_request_node it is now safe to send goals.
        # Publishing any earlier lets the new goal race the cancel result and
        # can break Nav2 comms.
        monitor.publish_patrol_stopped()
        should_resume = run_escort_goal_executor(navigator, monitor, lock)

        if not should_resume:
            break

        with monitor.lock:
            monitor.escort_requested = False
            monitor.escort_goal_name = None
            monitor.resume_requested = False

        navigator.info('Relay finished — undocking to resume patrol.')
        navigator.undock()

    monitor.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
