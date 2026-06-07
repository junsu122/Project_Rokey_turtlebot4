"""Vision 트랙 시뮬레이터 — IF-05 이상 상황 알림(FIRE/SUSPICIOUS_PERSON) 발행.

실제론 로봇 탑재 카메라 YOLO가 감지해 발행하는 메시지를 테스트에서 대신 쏜다.

실행 예:
    python3 tools/send_event.py --robot-id robot2 --type FIRE --confidence 0.91 --floor 1
    python3 tools/send_event.py --robot-id robot4 --type SUSPICIOUS_PERSON --confidence 0.78 --floor 2
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import messages  # noqa: E402
from transport import MqttTransport  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="IF-05 발행 (Vision 시뮬레이터)")
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--type", required=True, choices=["FIRE", "SUSPICIOUS_PERSON"])
    parser.add_argument("--confidence", type=float, default=0.9)
    parser.add_argument("--floor", type=int, default=1)
    parser.add_argument("--x", type=float, default=0.0)
    parser.add_argument("--y", type=float, default=0.0)
    parser.add_argument("--snapshot-ref", default=None)
    parser.add_argument("--broker-host", default=config.MQTT_HOST)
    parser.add_argument("--broker-port", type=int, default=config.MQTT_PORT)
    args = parser.parse_args()

    t = MqttTransport(host=args.broker_host, port=args.broker_port, client_id="vision_sim")
    t.connect(); t.loop_start(); time.sleep(0.3)

    msg = messages.if05(
        robot_id=args.robot_id,
        event_type=args.type,
        confidence=args.confidence,
        location={"x": args.x, "y": args.y, "floor": args.floor},
        snapshot_ref=args.snapshot_ref,
    )
    t.publish(config.topic_event(args.robot_id), msg, config.QOS_EVENT)
    print(f"▶ IF-05 {args.type}: {args.robot_id} (conf={args.confidence}, floor={args.floor})")

    time.sleep(0.5)
    t.loop_stop(); t.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
