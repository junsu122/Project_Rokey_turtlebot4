"""IF-05 이상 상황 알림 처리 — events 테이블 적재(기록 전용).

Vision 트랙(로봇 탑재 카메라 YOLO)이 감지한 FIRE/SUSPICIOUS_PERSON을 받아 적재한다.
미션과 무관한 독립 채널이다(미션 전이를 일으키지 않음). 관제 노출은 GET /api/events.

저장 정책(가이드 §6, README): 영상 원본은 저장하지 않고 메타데이터만.
snapshot_ref는 참조 키만 보관.
"""

from __future__ import annotations

import logging

import db
from states import EVENT_TYPES


logger = logging.getLogger("fms.event")


def record_event(payload: dict) -> None:
    """IF-05 → events 테이블 INSERT."""
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
        "INSERT INTO events(event_type, robot_id, confidence, x, y, floor, snapshot_ref, at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event_type, robot_id, payload.get("confidence"),
         loc.get("x"), loc.get("y"), loc.get("floor"),
         payload.get("snapshot_ref"), at),
    )
    logger.warning("IF-05 %s from %s (conf=%s, floor=%s) → 관제 노출",
                   event_type, robot_id, payload.get("confidence"), loc.get("floor"))
