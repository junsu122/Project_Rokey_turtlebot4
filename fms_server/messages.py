"""IF-01~05 + task_ack 메시지 빌더 — 공통 필드(msg_id/version/timestamp) 자동 부착.

계약 §2 공통 필드 규칙을 한곳에서 보장한다. FMS(IF-03 발행)와 mock_robot(IF-02 등)이
같은 빌더를 공유해 형식 일치를 강제한다.
"""

from __future__ import annotations

import uuid

import config
from db import utc_now_iso


def _envelope() -> dict:
    """모든 메시지 공통 필드 (계약 §2)."""
    return {
        "msg_id": uuid.uuid4().hex,
        "version": config.PROTOCOL_VERSION,
        "timestamp": utc_now_iso(),
    }


# ── IF-02: 로봇 상태 보고 (Robot → FMS) ─────────────────────────────────
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


# ── IF-03: 임무 할당 (FMS → Robot) ──────────────────────────────────────
def if03(
    task_id: str,
    robot_id: str,
    task_type: str,
    goal: dict,
    mission_id: str,
    customer: dict | None = None,
    cancel_task_id: str | None = None,
) -> dict:
    msg = _envelope()
    msg.update({
        "task_id": task_id,
        "robot_id": robot_id,
        "task_type": task_type,
        "goal": goal,
        "customer": customer or {},
        "mission_id": mission_id,
        "cancel_task_id": cancel_task_id,
    })
    return msg


# ── task_ack (Robot → FMS) ──────────────────────────────────────────────
def task_ack(task_id: str, robot_id: str, result: str) -> dict:
    msg = _envelope()
    msg.update({"task_id": task_id, "robot_id": robot_id, "result": result})
    return msg


# ── IF-01: 고객 요청 (Interaction → FMS) — 주로 테스트/도구용 ────────────
def if01(
    request_id: str,
    robot_id: str,
    destination: dict,
    origin: dict,
    customer: dict | None = None,
    request_type: str = "ESCORT",
    target_request_id: str | None = None,
) -> dict:
    msg = _envelope()
    msg.update({
        "request_id": request_id,
        "robot_id": robot_id,
        "request_type": request_type,
        "destination": destination,
        "origin": origin,
        "customer": customer or {},
        "target_request_id": target_request_id,
    })
    return msg


# ── IF-05: 이상 상황 알림 (Robot → FMS) ─────────────────────────────────
def if05(
    robot_id: str,
    event_type: str,
    confidence: float,
    location: dict,
    snapshot_ref: str | None = None,
) -> dict:
    msg = _envelope()
    msg.update({
        "event_type": event_type,
        "robot_id": robot_id,
        "confidence": confidence,
        "location": location,
        "snapshot_ref": snapshot_ref,
    })
    return msg
