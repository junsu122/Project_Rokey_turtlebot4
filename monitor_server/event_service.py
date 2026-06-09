"""Detector/event message ingestion.

The monitor stores event metadata only. It does not trigger missions or publish
commands back to robots.
"""

from __future__ import annotations

import logging

import db
from states import EVENT_TYPES


logger = logging.getLogger("fms.event")


def record_event(payload: dict) -> None:
    """Store IF-05 style detector events."""
    event_type = payload.get("event_type")
    robot_id = payload.get("robot_id")
    if event_type is None or robot_id is None:
        logger.warning("IF-05 missing event_type/robot_id: %s", payload)
        return
    # 관측만 — enum 밖이면 경고 후 그대로 기록
    if event_type not in EVENT_TYPES:
        logger.warning("unknown IF-05 event_type '%s' from %s", event_type, robot_id)

    loc = payload.get("location") or {}
    at = payload.get("timestamp") or db.utc_now_iso()
    db.execute(
        "INSERT INTO events(msg_id, event_type, event_class, robot_id, confidence, "
        "x, y, floor, snapshot_ref, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (payload.get("msg_id"), event_type, payload.get("class"), robot_id,
         payload.get("confidence"),
         loc.get("x"), loc.get("y"), loc.get("floor"),
         payload.get("snapshot_ref"), at),
    )
    logger.warning("event %s/%s from %s (conf=%s, floor=%s)",
                   event_type, payload.get("class"), robot_id,
                   payload.get("confidence"), loc.get("floor"))
