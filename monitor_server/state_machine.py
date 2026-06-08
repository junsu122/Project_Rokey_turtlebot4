"""Mission FSM — 전이표를 **데이터로** 들고 (정의서 §7 / 가이드 §5.1 코드화).

이 모듈은 "전이 자체"만 안다(순수 데이터+질의). task 발행·DB·타이밍 같은
액션과 I/O는 mission_manager가 담당한다. 절대 규칙 2: 이벤트 구동, 블로킹 없음.

이벤트 키 의미:
- ASSIGN                : IF-01 ESCORT 수신 후 두 로봇 배정
- DISPATCH_HANDOVER     : start에 ESCORT_TO_HANDOVER 발행(층 다름)
- DISPATCH_FINAL_DIRECT : start에 ESCORT_TO_FINAL 발행(같은 층 직행)
- START_ARRIVED         : start_robot이 핸드오버 지점 도착(WAITING_HANDOVER)
- HANDOVER_APPROVED     : start 도착 ∧ next 준비 → 인수 승인
- FINAL_ARRIVED         : next(또는 같은 층이면 start)가 최종 목적지 도착
"""

from __future__ import annotations

from states import (
    MISSION_ASSIGNED, MISSION_COMPLETED, MISSION_ESCORTING_TO_FINAL,
    MISSION_ESCORTING_TO_HANDOVER, MISSION_HANDOVER_WAITING, MISSION_REQUESTED,
    MISSION_CANCELLED, MISSION_EMERGENCY, MISSION_FAILED,
)


# ── 정상 전이표 (current_mission_state, event) → next_mission_state ──────
NORMAL_TRANSITIONS: dict[tuple[str, str], str] = {
    (MISSION_REQUESTED, "ASSIGN"): MISSION_ASSIGNED,
    (MISSION_ASSIGNED, "DISPATCH_HANDOVER"): MISSION_ESCORTING_TO_HANDOVER,
    (MISSION_ASSIGNED, "DISPATCH_FINAL_DIRECT"): MISSION_ESCORTING_TO_FINAL,
    (MISSION_ESCORTING_TO_HANDOVER, "START_ARRIVED"): MISSION_HANDOVER_WAITING,
    (MISSION_HANDOVER_WAITING, "HANDOVER_APPROVED"): MISSION_ESCORTING_TO_FINAL,
    (MISSION_ESCORTING_TO_FINAL, "FINAL_ARRIVED"): MISSION_COMPLETED,
}

# ── 예외 전이 (M3에서 사용) — 어느 진행 상태에서든 종결로 ────────────────
EXCEPTION_TARGET: dict[str, str] = {
    "CANCEL": MISSION_CANCELLED,
    "EMERGENCY": MISSION_EMERGENCY,
    "FAIL": MISSION_FAILED,
}

# 진행 중(종결 아님) 상태 — 예외 전이가 허용되는 상태
ACTIVE_STATES = {
    MISSION_REQUESTED, MISSION_ASSIGNED, MISSION_ESCORTING_TO_HANDOVER,
    MISSION_HANDOVER_WAITING, MISSION_ESCORTING_TO_FINAL,
}

TERMINAL_STATES = {
    MISSION_COMPLETED, MISSION_CANCELLED, MISSION_EMERGENCY, MISSION_FAILED,
}


def next_state(current: str, event: str) -> str | None:
    """정상 전이표 조회. 정의 안 된 (상태,이벤트)면 None(전이 없음)."""
    return NORMAL_TRANSITIONS.get((current, event))


def exception_state(event: str) -> str | None:
    return EXCEPTION_TARGET.get(event)
