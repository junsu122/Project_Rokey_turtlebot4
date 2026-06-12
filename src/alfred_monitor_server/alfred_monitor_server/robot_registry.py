"""ROS2 robot status ingestion.

Every RobotState message updates ``latest_robot_status`` in SQLite.
State/task-status changes are also appended to ``robot_status_log`` for history.
"""

from __future__ import annotations

import logging

from . import config
from . import store
from .states import ROBOT_STATES


logger = logging.getLogger("monitor.robot_status")


class RobotRegistry:
    def update_from_status(self, payload: dict) -> dict | None:
        robot_id = payload.get("robot_id")
        if not robot_id:
            logger.warning("robot status without robot_id: %s", payload)
            return None

        state = payload.get("state")
        if state is not None and state not in ROBOT_STATES:
            logger.warning("unknown robot state '%s' from %s", state, robot_id)

        pose = payload.get("pose") or {}
        battery = payload.get("battery")
        task_id = payload.get("current_task_id")
        task_status = payload.get("task_status")
        error_code = payload.get("error_code")
        now = store.utc_now()
        floor = config.ROBOTS.get(robot_id, {}).get("floor")

        prev = store.get_prev_status(robot_id)
        prev_state = prev.get("state") if prev else None
        prev_task_status = prev.get("task_status") if prev else None

        store.upsert_robot_status({
            "robot_id": robot_id,
            "floor": floor,
            "state": state,
            "battery": battery,
            "x": pose.get("x"),
            "y": pose.get("y"),
            "theta": pose.get("theta"),
            "current_task_id": task_id,
            "task_status": task_status,
            "error_code": error_code,
            "last_seen": now,
        })

        changed = (
            prev is None
            or prev_state != state
            or prev_task_status != task_status
        )
        if changed:
            store.append_status_log({
                "robot_id": robot_id,
                "state": state,
                "prev_state": prev_state,
                "task_id": task_id,
                "task_status": task_status,
                "battery": battery,
                "x": pose.get("x"),
                "y": pose.get("y"),
                "at": now,
            })
            if prev_state != state:
                logger.info("[%s] state %s -> %s (task=%s/%s)",
                            robot_id, prev_state, state, task_id, task_status)

        return {
            "robot_id": robot_id,
            "floor": floor,
            "state": state,
            "pose": pose,
            "battery": battery,
            "current_task_id": task_id,
            "task_status": task_status,
            "error_code": error_code,
            "last_seen": now,
        }

    def update_from_ros_state(self, msg) -> dict | None:
        pose = getattr(msg, "pose", None)
        payload = {
            "robot_id": getattr(msg, "robot_id", ""),
            "state": getattr(msg, "state", None),
            "pose": {
                "x": getattr(pose, "x", None),
                "y": getattr(pose, "y", None),
                "theta": getattr(pose, "theta", None),
            },
            "battery": getattr(msg, "battery", None),
            "current_task_id": getattr(msg, "current_task_id", None) or None,
            "task_status": getattr(msg, "task_status", None) or None,
            "error_code": getattr(msg, "error_code", None) or None,
            "timestamp": getattr(msg, "timestamp", None) or None,
        }
        return self.update_from_status(payload)
