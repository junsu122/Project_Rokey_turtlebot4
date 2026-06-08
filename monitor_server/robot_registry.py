"""로봇별 최신 IF-02 스냅샷 보관 + 상태 전이 감지 + 미수신(통신장애) 감시.

설계(구현가이드 §3, §6):
- 1~2Hz 주기 보고는 **메모리 최신값**만 유지(스냅샷).
- 상태/ task_status가 **변할 때만** robot_status_log에 INSERT (전이/변화 시에만).
- last_seen으로 미수신 감시 → STATUS_TIMEOUT 초과 시 stale (M3 타임아웃 처리에서 사용).

절대 규칙 5: Robot State는 로봇 소유. 여기선 관측·기록만 하고 명령하지 않는다.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

import config
import db
from states import ROBOT_STATES


logger = logging.getLogger("fms.registry")


class RobotRegistry:
    def __init__(self) -> None:
        self._snapshots: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ── IF-02 수신 처리 ─────────────────────────────────────────────────
    def update_from_status(self, payload: dict) -> dict | None:
        robot_id = payload.get("robot_id")
        if not robot_id:
            logger.warning("IF-02 without robot_id: %s", payload)
            return None

        state = payload.get("state")
        # 관측만 — enum 밖이면 경고 후 그대로 기록(거부 아님, 절대 규칙 5)
        if state is not None and state not in ROBOT_STATES:
            logger.warning("unknown robot state '%s' from %s", state, robot_id)

        pose = payload.get("pose") or {}
        battery = payload.get("battery")
        task_id = payload.get("current_task_id")
        task_status = payload.get("task_status")
        error_code = payload.get("error_code")
        now = db.utc_now_iso()

        with self._lock:
            prev = self._snapshots.get(robot_id)
            prev_state = prev.get("state") if prev else None
            prev_task_status = prev.get("task_status") if prev else None
            snap = {
                "robot_id": robot_id,
                "state": state,
                "pose": pose,
                "battery": battery,
                "current_task_id": task_id,
                "task_status": task_status,
                "error_code": error_code,
                "last_seen": now,
            }
            self._snapshots[robot_id] = snap
            changed = (
                prev is None
                or prev_state != state
                or prev_task_status != task_status
            )

        # 전이/변화 시에만 적재 (주기 보고는 메모리 최신값만 — 가이드 §6)
        if changed:
            db.execute(
                "INSERT INTO robot_status_log"
                "(robot_id, state, prev_state, task_id, task_status, battery, x, y, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (robot_id, state, prev_state, task_id, task_status, battery,
                 pose.get("x"), pose.get("y"), now),
            )
            if prev_state != state:
                logger.info("[%s] state %s → %s (task=%s/%s)",
                            robot_id, prev_state, state, task_id, task_status)
        return snap

    # ── 조회 (Flask API용) ──────────────────────────────────────────────
    def snapshot(self, robot_id: str) -> dict | None:
        with self._lock:
            snap = self._snapshots.get(robot_id)
            return dict(snap) if snap else None

    def all_snapshots(self) -> list[dict]:
        with self._lock:
            return [dict(s) for s in sorted(self._snapshots.values(),
                                            key=lambda s: s["robot_id"])]

    # ── 미수신 감시 (M3 타임아웃 처리에서 사용) ──────────────────────────
    def stale_robots(self, timeout_s: float | None = None) -> list[str]:
        """last_seen이 timeout을 초과한 robot_id 목록 (통신 장애 후보)."""
        timeout_s = timeout_s if timeout_s is not None else config.STATUS_TIMEOUT
        now = datetime.now(timezone.utc)
        stale: list[str] = []
        with self._lock:
            for robot_id, snap in self._snapshots.items():
                try:
                    last = datetime.fromisoformat(snap["last_seen"])
                except (ValueError, KeyError):
                    continue
                if (now - last).total_seconds() > timeout_s:
                    stale.append(robot_id)
        return stale
