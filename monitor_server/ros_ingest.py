"""ROS2 subscriptions that persist monitoring data into SQLite."""

from __future__ import annotations

import json
import logging

from rclpy.node import Node
from std_msgs.msg import String

import config
import event_service
import usage_service
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
            detection_topic = config.ros_detection_topic(robot_id)
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
            self._subscriptions.append(
                self.create_subscription(
                    String,
                    detection_topic,
                    self._on_detection_info,
                    config.ROS_QOS_EVENT,
                )
            )
            logger.info("subscribed ROS2 %s", status_topic)
            logger.info("subscribed ROS2 %s", event_topic)
            logger.info("subscribed ROS2 %s", detection_topic)

        self._subscriptions.append(
            self.create_subscription(
                String,
                config.ROS_INFORMATION_TOPIC,
                self._on_information,
                config.ROS_QOS_EVENT,
            )
        )
        logger.info("subscribed ROS2 %s", config.ROS_INFORMATION_TOPIC)

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

    def _on_detection_info(self, msg: String) -> None:
        payload = _loads_json_msg(msg, "detection/info")
        if payload is not None:
            event_service.record_event(payload)

    def _on_information(self, msg: String) -> None:
        payload = _loads_json_msg(msg, config.ROS_INFORMATION_TOPIC)
        if payload is None:
            return
        usage_service.record_information(_unwrap_rosbridge_payload(payload))


def _loads_json_msg(msg: String, source: str) -> dict | None:
    try:
        payload = json.loads(msg.data)
    except json.JSONDecodeError as err:
        logger.warning("invalid JSON on %s: %s", source, err)
        return None
    if not isinstance(payload, dict):
        logger.warning("non-object JSON on %s: %s", source, payload)
        return None
    return payload


def _unwrap_rosbridge_payload(payload: dict) -> dict:
    inner = payload.get("msg", payload)
    if isinstance(inner, dict) and "data" in inner and len(inner) == 1:
        try:
            decoded = json.loads(inner["data"])
        except (TypeError, json.JSONDecodeError):
            return inner
        return decoded if isinstance(decoded, dict) else inner
    return inner if isinstance(inner, dict) else payload
