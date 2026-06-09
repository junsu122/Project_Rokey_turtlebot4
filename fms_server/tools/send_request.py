"""Interaction 트랙 시뮬레이터 — IF-01 ESCORT 발행 (전체 시퀀스 시작점).

실제론 STT/LLM이 목적지를 확정해 발행하는 메시지를, 테스트에서 대신 쏜다.
기본 흐름: (호출 재현) 시작 로봇을 INTERACTING으로 만든 뒤 → IF-01 발행.

실행 예:
    python3 tools/send_request.py --robot-id robot2 --dest trans --dest-floor 2 --origin-floor 1
    python3 tools/send_request.py --robot-id robot2 --dest info --dest-floor 1 --origin-floor 1   # 같은 층 직행
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
    parser = argparse.ArgumentParser(description="IF-01 ESCORT 발행 (Interaction 시뮬레이터)")
    parser.add_argument("--robot-id", required=True, help="호출받은 로봇(=start_robot)")
    parser.add_argument("--dest", help="목적지 poi_id (예: trans, info) — ESCORT 시 필수")
    parser.add_argument("--dest-floor", type=int, help="ESCORT 시 필수")
    parser.add_argument("--origin-floor", type=int, default=1)
    parser.add_argument("--cancel", action="store_true",
                        help="진행 중 미션 취소(IF-01 CANCEL 발행)")
    parser.add_argument("--profile", default="GENERAL",
                        help="GENERAL|ELDERLY|FOREIGNER|VISUALLY_IMPAIRED")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--no-call", action="store_true",
                        help="호출(INTERACTING) 재현 생략하고 IF-01만 발행")
    parser.add_argument("--broker-host", default=config.MQTT_HOST)
    parser.add_argument("--broker-port", type=int, default=config.MQTT_PORT)
    args = parser.parse_args()

    t = MqttTransport(host=args.broker_host, port=args.broker_port,
                      client_id="interaction_sim")
    t.connect()
    t.loop_start()
    time.sleep(0.3)

    # 취소: IF-01 CANCEL 발행 후 종료
    if args.cancel:
        msg = messages.if01(
            request_id="REQ_CANCEL_" + str(int(time.time())),
            robot_id=args.robot_id,
            destination={}, origin={}, request_type="CANCEL",
        )
        t.publish(config.topic_request(args.robot_id), msg, config.QOS_REQUEST)
        print(f"▶ IF-01 CANCEL: {args.robot_id} 진행 미션 취소")
        time.sleep(0.5)
        t.loop_stop(); t.disconnect()
        return 0

    if not args.dest or args.dest_floor is None:
        parser.error("ESCORT 요청에는 --dest 와 --dest-floor 가 필요합니다")

    # 1) 고객 호출 재현 → start_robot을 INTERACTING으로 (FMS 관여 없는 로봇 로컬 전이)
    if not args.no_call:
        t.publish(f"mock/{args.robot_id}/cmd", {"cmd": "call"}, qos=1)
        print(f"▶ call → {args.robot_id} (PATROL→INTERACTING)")
        time.sleep(0.5)

    # 2) IF-01 ESCORT 발행
    request_id = "REQ_" + str(int(time.time()))
    msg = messages.if01(
        request_id=request_id,
        robot_id=args.robot_id,
        destination={"poi_id": args.dest, "floor": args.dest_floor},
        origin={"floor": args.origin_floor, "pose": {"x": 0.0, "y": 0.0}},
        customer={"customer_id": "C_demo", "profile": args.profile, "language": args.language},
    )
    t.publish(config.topic_request(args.robot_id), msg, config.QOS_REQUEST)
    print(f"▶ IF-01 ESCORT: {args.robot_id} → {args.dest}(floor {args.dest_floor}), "
          f"origin floor {args.origin_floor}, request_id={request_id}")

    time.sleep(0.5)  # 발행 완료 대기(QoS1 전달)
    t.loop_stop()
    t.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
