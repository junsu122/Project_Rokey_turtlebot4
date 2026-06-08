"""Small message helpers for monitoring tests and demos."""

from __future__ import annotations

import uuid

import config
from db import utc_now_iso


def _envelope() -> dict:
    return {
        "msg_id": uuid.uuid4().hex,
        "version": config.PROTOCOL_VERSION,
        "timestamp": utc_now_iso(),
    }


def if02(
    robot_id: str,
    state: str,
    pose: dict | None = None,
    battery: int | None = None,
    current_task_id: str | None = None,
    task_status: str | None = None,
    error_code: str | None = None,
) -> dict:
    msg = _envelope()
    msg.update({
        "robot_id": robot_id,
        "state": state,
        "pose": pose or {"x": 0.0, "y": 0.0, "theta": 0.0},
        "battery": battery,
        "current_task_id": current_task_id,
        "task_status": task_status,
        "error_code": error_code,
    })
    return msg


def if05(
    robot_id: str,
    event_type: str,
    confidence: float,
    location: dict,
    snapshot_ref: str | None = None,
    event_class: str | None = None,
) -> dict:
    msg = _envelope()
    msg.update({
        "event_type": event_type,
        "class": event_class,
        "robot_id": robot_id,
        "confidence": confidence,
        "location": location,
        "snapshot_ref": snapshot_ref,
    })
    return msg
