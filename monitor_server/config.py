"""Monitoring server configuration."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent

PROTOCOL_VERSION = "2.1"

# Robot metadata is informational only. No dispatch/control decisions are made.
ROBOTS: dict[str, dict] = {
    "robot2": {"namespace": "/robot2", "ros_domain_id": 2, "floor": 1},
    "robot4": {"namespace": "/robot4", "ros_domain_id": 2, "floor": 2},
}
ROBOT_IDS = list(ROBOTS)


def ros_robot_state_topic(robot_id: str) -> str:
    return f"/{robot_id}/robot_state"


def ros_event_topic(robot_id: str) -> str:
    return f"/{robot_id}/vision/alert"


def ros_detection_topic(robot_id: str) -> str:
    return f"/{robot_id}/detection/info"


ROS_INFORMATION_TOPIC = os.getenv("FMS_ROS_INFORMATION_TOPIC", "/information")

ROS_QOS_STATUS = int(os.getenv("FMS_ROS_QOS_STATUS", "10"))
ROS_QOS_EVENT = int(os.getenv("FMS_ROS_QOS_EVENT", "10"))

# Used only to mark dashboard freshness/offline status.
STATUS_TIMEOUT = float(os.getenv("FMS_STATUS_TIMEOUT", "10.0"))

DB_PATH = os.getenv("FMS_DB_PATH", str(BASE_DIR / "fms.db"))

# Storage backend for the ROS2 ingest pump: "sqlite" (local) or "supabase".
BACKEND = os.getenv("FMS_BACKEND", "sqlite").lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_TIMEOUT = float(os.getenv("SUPABASE_TIMEOUT", "8.0"))

FLASK_HOST = os.getenv("FMS_FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FMS_FLASK_PORT", "5000"))
CORS_ORIGINS = os.getenv("FMS_CORS_ORIGINS", "*")

ADMIN_USER = os.getenv("FMS_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("FMS_ADMIN_PASSWORD", "admin1234")
SECRET_KEY = os.getenv("FMS_SECRET_KEY", "")

POI_TABLE_PATH = Path(os.getenv("FMS_POI_TABLE", str(BASE_DIR / "poi_table.yaml")))


def load_poi_table() -> dict[str, dict]:
    if not POI_TABLE_PATH.exists():
        return {}
    with POI_TABLE_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    pois = data.get("pois", {})
    return pois if isinstance(pois, dict) else {}
