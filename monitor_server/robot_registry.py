"""ROS2 robot status ingestion.

Every RobotState message updates ``latest_robot_status`` in SQLite.
State/task-status changes are also appended to ``robot_status_log`` for history.
"""

from __future__ import annotations

import logging

import config
import db
from states import ROBOT_STATES


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
        now = db.utc_now_iso()
        floor = config.ROBOTS.get(robot_id, {}).get("floor")

        prev = db.query_one(
            "SELECT state, task_status FROM latest_robot_status WHERE robot_id=?",
            (robot_id,),
        )
        prev_state = prev.get("state") if prev else None
        prev_task_status = prev.get("task_status") if prev else None

        db.execute(
            "INSERT INTO latest_robot_status"
            "(robot_id, floor, state, battery, x, y, theta, current_task_id, "
            "task_status, error_code, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(robot_id) DO UPDATE SET "
            "floor=excluded.floor, state=excluded.state, battery=excluded.battery, "
            "x=excluded.x, y=excluded.y, theta=excluded.theta, "
            "current_task_id=excluded.current_task_id, task_status=excluded.task_status, "
            "error_code=excluded.error_code, last_seen=excluded.last_seen",
            (
                robot_id,
                floor,
                state,
                battery,
                pose.get("x"),
                pose.get("y"),
                pose.get("theta"),
                task_id,
                task_status,
                error_code,
                now,
            ),
        )

        changed = (
            prev is None
            or prev_state != state
            or prev_task_status != task_status
        )
        if changed:
            db.execute(
                "INSERT INTO robot_status_log"
                "(robot_id, state, prev_state, task_id, task_status, battery, x, y, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    robot_id,
                    state,
                    prev_state,
                    task_id,
                    task_status,
                    battery,
                    pose.get("x"),
                    pose.get("y"),
                    now,
                ),
            )
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
