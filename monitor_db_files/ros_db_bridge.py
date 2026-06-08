#!/usr/bin/env python3
"""ROS2 → SQLite bridge for standalone viz_3d monitoring.

Use this when robot/detector data is already available as ROS2 topics.
MQTT is intentionally not used here.  MQTT can stay reserved for future user UI
inputs if that UI decides to publish through a broker.

Subscribed by default:
- /robot2/detection/info, /robot4/detection/info   std_msgs/String JSON
- /robot2/robot_state, /robot4/robot_state         alfred_interfaces/RobotState
- /robot2/ui/request, /robot4/ui/request           alfred_interfaces/Request
- /mission/state, /mission/status, /mission/event  std_msgs/String JSON
"""

from __future__ import annotations

import json
import logging

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import monitor_db as db
from db_bridge import detection_class, location, normalized_event_type, snapshot_ref, threat_type

try:
    from alfred_interfaces.msg import Request, RobotState
except ImportError:
    Request = None
    RobotState = None


logger = logging.getLogger("viz_3d.ros_db_bridge")


def pose2d_to_dict(pose) -> dict:
    return {
        "x": float(getattr(pose, "x", 0.0)),
        "y": float(getattr(pose, "y", 0.0)),
        "theta": float(getattr(pose, "theta", 0.0)),
    }


def customer_from_request(msg) -> dict:
    return {
        "customer_id": msg.customer_id or None,
        "profile": msg.customer_profile or None,
        "language": msg.customer_language or None,
    }


class RosDbBridge(Node):
    def __init__(self) -> None:
        super().__init__("ros_db_bridge")
        db.init_db()
        db.seed_default_robots()

        self.declare_parameter("robot_ids", ["robot2", "robot4"])
        self.robot_ids = list(self.get_parameter("robot_ids").value)
        self._subs = []

        for robot_id in self.robot_ids:
            self._subs.append(
                self.create_subscription(
                    String,
                    f"/{robot_id}/detection/info",
                    lambda msg, rid=robot_id: self._on_detection(rid, msg),
                    10,
                )
            )

            if RobotState is not None:
                self._subs.append(
                    self.create_subscription(
                        RobotState,
                        f"/{robot_id}/robot_state",
                        lambda msg, rid=robot_id: self._on_robot_state(rid, msg),
                        10,
                    )
                )

            if Request is not None:
                self._subs.append(
                    self.create_subscription(
                        Request,
                        f"/{robot_id}/ui/request",
                        lambda msg, rid=robot_id: self._on_request(rid, msg),
                        10,
                    )
                )

        for topic in ("/mission/state", "/mission/status", "/mission/event"):
            self._subs.append(self.create_subscription(String, topic, self._on_mission_json, 10))

        if RobotState is None or Request is None:
            self.get_logger().warning(
                "alfred_interfaces import failed. detection/info와 mission JSON만 받습니다. "
                "RobotState/Request까지 쓰려면 colcon build 후 source install/setup.bash 하세요."
            )

        self.get_logger().info(f"ROS DB bridge ready: robot_ids={self.robot_ids}")

    def _on_detection(self, fallback_robot_id: str, msg: String) -> None:
        payload = self._parse_json(msg.data, "detection/info")
        if payload is None:
            return
        payload.setdefault("robot_id", fallback_robot_id)
        self._save_detection(payload)

    def _save_detection(self, payload: dict) -> None:
        event_type = normalized_event_type(payload)
        if event_type is None:
            self.get_logger().warning(f"unknown detection payload={payload}")
            return

        floor, zone, location_name, x, y = location(payload)
        event_id = db.record_monitor_event(
            event_type=event_type,
            source_type="detector",
            source_id=payload.get("robot_id"),
            robot_id=payload.get("robot_id"),
            mission_id=payload.get("mission_id"),
            detection_class=detection_class(payload),
            threat_type=threat_type(payload),
            floor=floor,
            zone=zone,
            location_name=location_name,
            x=x,
            y=y,
            confidence=payload.get("confidence"),
            snapshot_ref=snapshot_ref(payload),
            payload=payload,
            at=payload.get("timestamp"),
        )
        self.get_logger().info(
            f"saved detection {event_id}: {event_type} robot={payload.get('robot_id')} "
            f"floor={floor} x={x} y={y} snapshot={snapshot_ref(payload)}"
        )

    def _on_robot_state(self, fallback_robot_id: str, msg) -> None:
        robot_id = msg.robot_id or fallback_robot_id
        payload = {
            "robot_id": robot_id,
            "state": msg.state,
            "pose": pose2d_to_dict(msg.pose),
            "battery": int(msg.battery),
            "current_task_id": msg.current_task_id or None,
            "task_status": msg.task_status or None,
            "error_code": msg.error_code or None,
            "timestamp": msg.timestamp or db.utc_now_iso(),
        }
        db.record_robot_status(payload)
        self.get_logger().debug(f"saved robot state: {robot_id} {msg.state}")

    def _on_request(self, fallback_robot_id: str, msg) -> None:
        robot_id = msg.robot_id or fallback_robot_id
        payload = {
            "request_id": msg.request_id,
            "robot_id": robot_id,
            "request_robot": robot_id,
            "request_type": msg.request_type,
            "mission_state": "REQUESTED",
            "destination_id": msg.dest_poi_id,
            "dest_floor": int(msg.dest_floor),
            "origin_floor": int(msg.origin_floor),
            "origin": {
                "floor": int(msg.origin_floor),
                "pose": pose2d_to_dict(msg.origin_pose),
            },
            "customer": customer_from_request(msg),
            "language": msg.customer_language or None,
            "target_request_id": msg.target_request_id or None,
            "timestamp": msg.timestamp or None,
        }
        if msg.request_id:
            payload["mission_id"] = msg.request_id
            db.upsert_mission(payload)
        db.record_monitor_event(
            event_type=db.EVENT_USER_INTERACTION,
            source_type="ros_ui",
            source_id=robot_id,
            robot_id=robot_id,
            mission_id=payload.get("mission_id"),
            language=msg.customer_language or None,
            payload=payload,
            at=msg.timestamp or None,
        )
        if msg.request_type == "ESCORT":
            db.record_monitor_event(
                event_type=db.EVENT_ESCORT_STARTED,
                source_type="ros_ui",
                source_id=robot_id,
                robot_id=robot_id,
                mission_id=payload.get("mission_id"),
                language=msg.customer_language or None,
                payload=payload,
                at=msg.timestamp or None,
            )
        self.get_logger().info(f"saved UI request: robot={robot_id} dest={msg.dest_poi_id}")

    def _on_mission_json(self, msg: String) -> None:
        payload = self._parse_json(msg.data, "mission JSON")
        if payload is None:
            return
        if not payload.get("mission_id"):
            self.get_logger().warning("mission JSON ignored: mission_id missing")
            return
        db.upsert_mission(payload)
        event_type = str(payload.get("event_type") or payload.get("state") or payload.get("mission_state") or "").upper()
        if event_type in ("COMPLETED", "MISSION_COMPLETED", "ESCORT_COMPLETED"):
            db.record_monitor_event(
                event_type=db.EVENT_ESCORT_COMPLETED,
                source_type="ros_mission",
                source_id=payload.get("robot_id"),
                robot_id=payload.get("robot_id"),
                mission_id=payload.get("mission_id"),
                payload=payload,
                at=payload.get("timestamp"),
            )
        self.get_logger().info(f"saved mission state: {payload.get('mission_id')} {event_type}")

    def _parse_json(self, data: str, label: str) -> dict | None:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            self.get_logger().warning(f"ignored non-JSON {label}")
            return None
        if not isinstance(payload, dict):
            self.get_logger().warning(f"ignored non-object JSON {label}")
            return None
        return payload


def main(args=None) -> None:
    logging.basicConfig(level=logging.INFO)
    rclpy.init(args=args)
    node = RosDbBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        db.close()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
