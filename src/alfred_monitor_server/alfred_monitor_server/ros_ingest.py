"""ROS2 subscriptions that persist monitoring data into SQLite."""

from __future__ import annotations

import json
import logging

from rclpy.node import Node
from std_msgs.msg import Empty, String

from . import config
from . import event_service
from . import usage_service
from alfred_interfaces.msg import RobotState
from .robot_registry import RobotRegistry


logger = logging.getLogger("monitor.ros")


class RosIngestNode(Node):
    def __init__(self, registry: RobotRegistry) -> None:
        # 노드 이름에 백엔드 접미사 — sqlite 대시보드와 supabase 펌프를 동시에 띄울 때
        # 같은 노드 이름이면 ROS2 discovery/구독이 충돌해 한쪽이 메시지를 못 받는다.
        super().__init__(f"monitor_server_ros_ingest_{config.BACKEND}")
        self.registry = registry
        self._subscriptions = []

        for robot_id in config.ROBOT_IDS:
            status_topic = config.ros_robot_state_topic(robot_id)
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
                    String,
                    detection_topic,
                    self._on_detection_info,
                    config.ROS_QOS_EVENT,
                )
            )
            logger.info("subscribed ROS2 %s", status_topic)
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

        # emergency_resolve 퍼블리셔 — 조치완료 버튼이 누리면 해당 로봇에 발행
        self._emergency_resolve_pubs: dict[str, object] = {
            robot_id: self.create_publisher(Empty, f"/{robot_id}/emergency_resolve", 1)
            for robot_id in config.ROBOT_IDS
        }

    def publish_emergency_resolve(self, robot_id: str) -> bool:
        """조치완료 버튼 → 해당 로봇 핸들러에게 emergency_resolve 신호 발행."""
        pub = self._emergency_resolve_pubs.get(robot_id)
        if pub is None:
            logger.warning("emergency_resolve: unknown robot_id '%s'", robot_id)
            return False
        pub.publish(Empty())
        logger.info("published /%s/emergency_resolve", robot_id)
        return True

    def _on_robot_state(self, msg: RobotState) -> None:
        self.registry.update_from_ros_state(msg)

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
