"""Detector/event message ingestion.

The monitor stores event metadata only. It does not trigger missions or publish
commands back to robots.
"""

from __future__ import annotations

import logging

from . import store
from .states import EVENT_TYPE_ALIASES, EVENT_TYPES


logger = logging.getLogger("fms.event")


def record_event(payload: dict) -> None:
    """Store IF-05 style detector events."""
    event_type = EVENT_TYPE_ALIASES.get(payload.get("event_type"), payload.get("event_type"))
    robot_id = payload.get("robot_id")
    if event_type is None or robot_id is None:
        logger.warning("IF-05 missing event_type/robot_id: %s", payload)
        return
    # 관측만 — enum 밖이면 경고 후 그대로 기록
    if event_type not in EVENT_TYPES:
        logger.warning("unknown IF-05 event_type '%s' from %s", event_type, robot_id)

    loc = payload.get("location") or {}
    at = payload.get("timestamp") or store.utc_now()
    store.insert_event({
        "msg_id": payload.get("msg_id"),
        "event_type": event_type,
        "event_class": payload.get("class"),
        "robot_id": robot_id,
        "confidence": payload.get("confidence"),
        "x": loc.get("x"),
        "y": loc.get("y"),
        "floor": loc.get("floor"),
        "snapshot_ref": payload.get("snapshot_ref"),
        "at": at,
    })
    logger.warning("event %s/%s from %s (conf=%s, floor=%s)",
                   event_type, payload.get("class"), robot_id,
                   payload.get("confidence"), loc.get("floor"))
