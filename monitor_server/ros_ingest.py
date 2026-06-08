"""ROS2 subscriptions that persist monitoring data into SQLite."""

from __future__ import annotations

import logging

from rclpy.node import Node

import config
import event_service
from alfred_interfaces.msg import Event, RobotState
from robot_registry import RobotRegistry


logger = logging.getLogger("monitor.ros")


class RosIngestNode(Node):
    def __init__(self, registry: RobotRegistry) -> None:
        super().__init__("monitor_server_ros_ingest")
        self.registry = registry
        self._subscriptions = []

        for robot_id in config.ROBOT_IDS:
            status_topic = config.ros_robot_state_topic(robot_id)
            event_topic = config.ros_event_topic(robot_id)
            self._subscriptions.append(
                self.create_subscription(
                    RobotState,
                    status_topic,
                    self._on_robot_state,
                    config.ROS_QOS_STATUS,
                )
            )
            self._subscriptions.append(
                self.create_subscription(
                    Event,
                    event_topic,
                    self._on_event,
                    config.ROS_QOS_EVENT,
                )
            )
            logger.info("subscribed ROS2 %s", status_topic)
            logger.info("subscribed ROS2 %s", event_topic)

    def _on_robot_state(self, msg: RobotState) -> None:
        self.registry.update_from_ros_state(msg)

    def _on_event(self, msg: Event) -> None:
        location = getattr(msg, "location", None)
        event_service.record_event({
            "event_type": getattr(msg, "event_type", None),
            "class": getattr(msg, "event_class", None) or getattr(msg, "class_name", None),
            "robot_id": getattr(msg, "robot_id", None),
            "confidence": getattr(msg, "confidence", None),
            "location": {
                "x": getattr(location, "x", None),
                "y": getattr(location, "y", None),
                "floor": getattr(msg, "floor", None),
            },
            "snapshot_ref": getattr(msg, "snapshot_ref", None) or None,
            "timestamp": getattr(msg, "timestamp", None) or None,
        })
