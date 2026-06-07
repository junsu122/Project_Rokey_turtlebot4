#!/usr/bin/env python3
"""FMS 계약 — 상태 enum·메시지 포맷·MQTT 토픽 (단일 출처: fms_server).

이 패키지는 FMS와 같은 워크스페이스(test_alfred) 안에 있다는 전제로
fms_server/states.py 를 **그대로 import** 한다 — robot state 값이 두 군데서
따로 손볼 일이 없도록(계약 변경 시 fms_server 쪽만 고치면 자동 반영).
states.py는 외부 의존성이 없는 순수 상수 모듈이라 가져오기 안전하다.

반면 fms_server/messages.py 는 import하지 않는다 — 그 모듈은 FMS의
config/db(POI 테이블 로드, FMS 전용 환경변수 등)까지 끌고 들어와 로봇
프로세스에는 무겁고 부적절하다. 대신 동일한 envelope·필드 형식을
이 파일에서 가볍게 재구현한다(아래 build_if02/build_task_ack).

다른 머신에 단독 배포할 경우, 아래 _FMS_SERVER_DIR 한 곳만
(예: vendored copy 경로로) 바꾸면 된다.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── fms_server/states.py를 단일 출처로 import ────────────────────────────
# colcon이 ament_python 패키지를 site-packages로 *복사 설치*하면 __file__이
# source tree 밖에 놓여 형제 디렉터리인 fms_server를 더 이상 추정할 수 없다
# (--symlink-install이면 __file__이 source로 resolve되어 추정이 들어맞지만,
#  최신 setuptools(>=60)에서 'option --editable not recognized'로 깨지는
#  환경이 있다). 그래서 FMS_SERVER_DIR 환경변수를 1순위로 보고, 없을 때만
# source-tree 레이아웃(현재 파일 기준 ../../fms_server)을 추정해 보강한다 —
# 이는 docstring에서 말한 "다른 머신에 단독 배포 시 한 곳만 바꾸면 된다"의
# 그 '한 곳'이기도 하다.
_env_dir = os.environ.get('FMS_SERVER_DIR')
_FMS_SERVER_DIR = Path(_env_dir) if _env_dir else Path(__file__).resolve().parents[2] / 'fms_server'
if not (_FMS_SERVER_DIR / 'states.py').is_file():
    raise ModuleNotFoundError(
        f"fms_server/states.py를 찾지 못했습니다 (확인 경로: {_FMS_SERVER_DIR}).\n"
        "  → 설치된 패키지(copy-install)에서는 source 위치를 추정할 수 없습니다.\n"
        "  → 실행 전에 다음과 같이 alfred_ws/fms_server 경로를 알려주세요:\n"
        "      export FMS_SERVER_DIR=/home/junsu/alfred_ws_handoff/alfred_ws/fms_server"
    )
if str(_FMS_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_FMS_SERVER_DIR))

from states import (  # noqa: E402  (sys.path 설정 후에만 import 가능)
    ROBOT_IDLE, ROBOT_PATROL, ROBOT_INTERACTING, ROBOT_RESERVED,
    ROBOT_HANDOVER_READY, ROBOT_ESCORTING, ROBOT_WAITING_HANDOVER,
    ROBOT_RETURNING, ROBOT_EMERGENCY, ROBOT_ERROR, ROBOT_STATES,
    TASK_MOVE_TO_STANDBY, TASK_ESCORT_TO_HANDOVER, TASK_ESCORT_TO_FINAL,
    TASK_RETURN_TO_BASE, TASK_TYPES, ESCORT_TASK_TYPES,
    TS_ACCEPTED, TS_RUNNING, TS_SUCCEEDED, TS_FAILED, TASK_STATUS,
    ACK_ACCEPT, ACK_REJECT,
)

PROTOCOL_VERSION = '2.1'

# ── task_type → 진행 중 / 완료 시 robot state ─────────────────────────────
# 출처: docs/INTERFACE_CONTRACT.md §6.1 "도착 후 로봇 동작" +
#       fms_server/tools/mock_robot.py TASK_PROGRESS_STATE/TASK_DONE_STATE
#       (FMS가 기대하는 robot state 전이의 참조 구현 — 이 표가 핵심 계약이다)
TASK_PROGRESS_STATE: dict[str, str] = {
    TASK_MOVE_TO_STANDBY:    ROBOT_RESERVED,
    TASK_ESCORT_TO_HANDOVER: ROBOT_ESCORTING,
    TASK_ESCORT_TO_FINAL:    ROBOT_ESCORTING,
    TASK_RETURN_TO_BASE:     ROBOT_RETURNING,
}
TASK_DONE_STATE: dict[str, str] = {
    TASK_MOVE_TO_STANDBY:    ROBOT_HANDOVER_READY,   # 후속 task(ESCORT_TO_FINAL) 대기
    TASK_ESCORT_TO_HANDOVER: ROBOT_WAITING_HANDOVER, # 핸드오버 지점 도착, 대기
    TASK_ESCORT_TO_FINAL:    ROBOT_ESCORTING,        # FMS가 곧 RETURN_TO_BASE를 내림
    TASK_RETURN_TO_BASE:     ROBOT_PATROL,           # task 완전 종료 → 순찰(기본 동작)
}

# 거절 판단 기준(계약 §6.2): "지금 임무 없이 대기 중인가" — PATROL/IDLE만 해당.
IDLE_LIKE = (ROBOT_PATROL, ROBOT_IDLE)


# ── MQTT 토픽 (fms_server/config.py 와 동일 규칙) ─────────────────────────
def topic_status(robot_id: str) -> str:
    return f'robot/{robot_id}/status'


def topic_task(robot_id: str) -> str:
    return f'robot/{robot_id}/task'


def topic_task_ack(robot_id: str) -> str:
    return f'robot/{robot_id}/task_ack'


# QoS — 정의서 §9.1과 동일(IF-02는 유실 허용 0, task/ack는 보장 1)
QOS_STATUS = 0
QOS_TASK = 1
QOS_TASK_ACK = 1


# ── 메시지 빌더 (messages.py와 동일 envelope·필드 — 로컬 재구현) ─────────
def _envelope() -> dict:
    return {
        'msg_id': uuid.uuid4().hex,
        'version': PROTOCOL_VERSION,
        'timestamp': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
    }


def build_if02(robot_id: str, state: str, pose: dict | None = None,
               battery: int | None = None, current_task_id: str | None = None,
               task_status: str | None = None, error_code: str | None = None) -> dict:
    msg = _envelope()
    msg.update({
        'robot_id': robot_id,
        'state': state,
        'pose': pose or {'x': 0.0, 'y': 0.0, 'theta': 0.0},
        'battery': battery,
        'current_task_id': current_task_id,
        'task_status': task_status,
        'error_code': error_code,
    })
    return msg


def build_task_ack(task_id: str, robot_id: str, result: str) -> dict:
    msg = _envelope()
    msg.update({'task_id': task_id, 'robot_id': robot_id, 'result': result})
    return msg
