"""M0 에코 테스트 — transport.py로 임의 토픽 pub/sub 왕복 확인.

사용:
  1) Mosquitto 기동:  sudo systemctl start mosquitto   (또는 mosquitto -d)
  2) python3 tools/echo_test.py

기대 출력: 발행한 메시지가 같은 토픽 구독 콜백으로 되돌아오면 성공.
이 스크립트는 paho를 직접 쓰지 않고 transport.MqttTransport만 사용한다(격리 검증).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# fms_server 패키지 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from db import utc_now_iso  # noqa: E402
from transport import MqttTransport  # noqa: E402


TEST_TOPIC = "fms/echo/test"
_received: list[dict] = []


def on_echo(topic: str, payload: dict) -> None:
    print(f"  ◀ received on {topic}: {payload}")
    _received.append(payload)


def main() -> int:
    t = MqttTransport(client_id="fms_echo_test")
    t.connect()
    t.loop_start()
    time.sleep(0.5)  # 연결 안정화 대기 (테스트 스크립트 한정)

    t.subscribe(TEST_TOPIC, on_echo, qos=1)
    time.sleep(0.3)

    msg = {
        "msg_id": "echo-1",
        "version": config.PROTOCOL_VERSION,
        "text": "hello fms",
        "timestamp": utc_now_iso(),
    }
    print(f"  ▶ publishing to {TEST_TOPIC}: {msg}")
    t.publish(TEST_TOPIC, msg, qos=1)

    # 왕복 수신 대기 (폴링은 테스트 스크립트 한정 — 서버 본체는 이벤트 구동)
    deadline = time.time() + 3.0
    while time.time() < deadline and not _received:
        time.sleep(0.05)

    t.loop_stop()
    t.disconnect()

    if _received:
        print("✅ M0 echo OK — MQTT pub/sub 왕복 성공")
        return 0
    print("❌ echo 실패 — Mosquitto 기동 여부/브로커 주소 확인")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
