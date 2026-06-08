"""FMS 전역 설정 — 브로커 주소, MQTT 토픽, 타임아웃 상수, POI 테이블 로드.

구현가이드 §3: "타임아웃 상수는 config.py에 모은다."
환경변수로 override 가능(시연 PC 별 IP 차이 흡수).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent

# ── 프로토콜 공통 (인터페이스 정의서 v2.1 / 구현가이드 §4.1) ──────────────
# 공통 필드 version 값. 가이드 §4.1 기준 "2.1"로 통일(정의서 예시의 "2.0"보다 우선).
PROTOCOL_VERSION = "2.1"

# ── MQTT 브로커 (구현가이드 §4) ───────────────────────────────────────────
MQTT_HOST = os.getenv("FMS_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("FMS_MQTT_PORT", "1883"))
MQTT_KEEPALIVE = int(os.getenv("FMS_MQTT_KEEPALIVE", "60"))
MQTT_CLIENT_ID = os.getenv("FMS_MQTT_CLIENT_ID", "fms_server")

# ── 로봇 레지스트리 (시연 전제: 2대, 미션당 전속) ────────────────────────
# 각 항목이 자기완결적 프로파일 = 복제/교체 단위("카피"의 단위).
#
# ⚠️ ros_domain_id는 FMS가 사용하지 않는 **정보 필드**다(절대 규칙 1: FMS는 ROS 비의존).
#    브리지/mock 실행 스크립트가 단일 출처로 참조하라고 둔 값일 뿐, FMS는 MQTT만 본다.
#    → 도메인 분리(현재 공유 2 → 개별)는 이 값과 브리지 환경변수만 바뀌고 FMS 코드는 불변.
#
# robot_id는 ROS 네임스페이스와 동일하게 둬서 brige의 robot2→A 같은 번역을 없앤다.
# start_robot ↔ next_robot은 식별자가 아니라 **미션별 역할**이다(partner_of로 동적 결정).
ROBOTS: dict[str, dict] = {
    "robot2": {
        "namespace": "/robot2",
        "ros_domain_id": 2,      # 현재 공유. 분리 후 개별 값으로 교체(브리지 측).
        "base_poi": "station",   # 복귀(충전/대기) 지점 — poi_table.yaml type=BASE(robot2)
    },
    "robot4": {
        "namespace": "/robot4",
        "ros_domain_id": 2,      # 현재 공유.
        "base_poi": "station2",  # poi_table.yaml type=BASE(robot4)
    },
}
ROBOT_IDS = list(ROBOTS)


def partner_of(robot_id: str) -> str | None:
    """상대 로봇 반환. 동시 고객 1명·2대 전제에서 호출 로봇의 상대가 곧 next_robot.

    레지스트리 기반이라 로봇을 추가/교체해도 코드 불변(3대 이상 시 배정 로직은 부록 C).
    """
    others = [rid for rid in ROBOT_IDS if rid != robot_id]
    return others[0] if len(others) == 1 else None

# ── MQTT 토픽 명세 (구현가이드 §4 / 정의서 §9.1) ─────────────────────────
# {id} ∈ {A, B}. FMS는 와일드카드(robot/+/...)로 일괄 구독한다.
def topic_status(robot_id: str) -> str:
    return f"robot/{robot_id}/status"


def topic_request(robot_id: str) -> str:
    return f"robot/{robot_id}/request"


def topic_event(robot_id: str) -> str:
    return f"robot/{robot_id}/event"


def topic_task(robot_id: str) -> str:
    return f"robot/{robot_id}/task"


def topic_task_ack(robot_id: str) -> str:
    return f"robot/{robot_id}/task_ack"


# 구독용 와일드카드 (로봇→FMS 채널 일괄 구독)
TOPIC_STATUS_WILDCARD = "robot/+/status"
TOPIC_REQUEST_WILDCARD = "robot/+/request"
TOPIC_EVENT_WILDCARD = "robot/+/event"
TOPIC_TASK_ACK_WILDCARD = "robot/+/task_ack"

# ── QoS (정의서 §9.1: IF-02=유실허용 0, IF-01/03/05=보장 1) ──────────────
QOS_STATUS = 0     # IF-02 주기 보고 — 유실 허용
QOS_REQUEST = 1    # IF-01 — 보장 필수
QOS_TASK = 1       # IF-03 — 보장 필수
QOS_TASK_ACK = 1   # task_ack — 보장 필수
QOS_EVENT = 1      # IF-05 — 보장 필수

# ── 타임아웃·측정 상수 (단위: 초) ────────────────────────────────────────
# robot status 미수신 감시. 초과 시 mission FAILED + 로봇 ERROR 표기 (정의서 §7 예외).
STATUS_TIMEOUT = float(os.getenv("FMS_STATUS_TIMEOUT", "10.0"))
# task_ack 로깅용(재전송 정책은 스코프 아웃 — 가이드 §4).
TASK_ACK_TIMEOUT = float(os.getenv("FMS_TASK_ACK_TIMEOUT", "3.0"))
# 타임아웃 감시 스레드 주기.
STATUS_WATCH_INTERVAL = float(os.getenv("FMS_STATUS_WATCH_INTERVAL", "1.0"))
# 핸드오버 수락 기준(수락 기준 = 3초). 측정·증빙용 기준값(차단용 아님).
HANDOVER_TARGET_MS = int(os.getenv("FMS_HANDOVER_TARGET_MS", "3000"))

# ── DB (SQLite WAL) ──────────────────────────────────────────────────────
DB_PATH = os.getenv("FMS_DB_PATH", str(BASE_DIR / "fms.db"))

# ── Flask (읽기 전용 조회 API, 별도 스레드) ──────────────────────────────
FLASK_HOST = os.getenv("FMS_FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FMS_FLASK_PORT", "5000"))
CORS_ORIGINS = os.getenv("FMS_CORS_ORIGINS", "*")

# ── 관제 UI 로그인 (system monitor 평가지표) ─────────────────────────────
ADMIN_USER = os.getenv("FMS_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("FMS_ADMIN_PASSWORD", "admin1234")  # 운영 시 env로 교체
# 세션 서명 키. 비우면 기동 시 랜덤 생성(재시작하면 재로그인 필요).
SECRET_KEY = os.getenv("FMS_SECRET_KEY", "")

# ── POI 테이블 (poi_id → 표시명/floor/pose) ─────────────────────────────
# 값은 맵 작성 후 채움(스코프 §9). 현재는 구조 스텁.
POI_TABLE_PATH = Path(os.getenv("FMS_POI_TABLE", str(BASE_DIR / "poi_table.yaml")))


def load_poi_table() -> dict[str, dict]:
    """poi_table.yaml 로드 → {poi_id: {...}} 딕셔너리.

    파일이 없거나 비어 있으면 빈 dict 반환(맵 미작성 단계 허용).
    """
    if not POI_TABLE_PATH.exists():
        return {}
    with POI_TABLE_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    pois = data.get("pois", {})
    return pois if isinstance(pois, dict) else {}
