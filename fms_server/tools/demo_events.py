"""데모용 IF-05 일괄 발행 — 여러 이상감지를 한 번에 쏜다(랜덤 타입·좌표).

실제 로봇 YOLO 가 발행할 IF-05 메시지를 시뮬레이터로 여러 건 대신 쏜다.
좌표는 각 층 맵 보정 중심(viz_3d ROS_CALIB) 근처로 흩뿌려 3D 비콘이 맵 위에 뜨게 한다.

실행 예:
    python3 tools/demo_events.py                 # 기본 8건, 두 층 랜덤
    python3 tools/demo_events.py --count 20 --interval 0.2
    python3 tools/demo_events.py --floor 1 --types FIRE EMERGENCY_PATIENT
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import messages  # noqa: E402
from transport import MqttTransport  # noqa: E402

ALL_TYPES = ["FIRE", "SUSPICIOUS_PERSON", "EMERGENCY_PATIENT"]

# 층별: 담당 로봇 + 맵 보정 중심(cx,cy) + 흩뿌릴 반경(rx,ry). viz_3d ROS_CALIB 와 동일 기준.
FLOORS = {
    1: {"robot_id": "robot2", "cx": -4.545, "cy": 2.59, "rx": 3.0, "ry": 1.8},
    2: {"robot_id": "robot4", "cx": -1.71, "cy": 2.34, "rx": 1.4, "ry": 1.1},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="IF-05 데모 일괄 발행")
    parser.add_argument("--count", type=int, default=8, help="발행할 이벤트 수")
    parser.add_argument("--interval", type=float, default=0.4, help="발행 간격(초)")
    parser.add_argument("--floor", type=int, choices=[1, 2], default=None,
                        help="특정 층만(미지정 시 두 층 랜덤)")
    parser.add_argument("--types", nargs="+", choices=ALL_TYPES, default=ALL_TYPES,
                        help="발행할 이벤트 타입 후보")
    parser.add_argument("--seed", type=int, default=None, help="재현용 난수 시드")
    parser.add_argument("--broker-host", default=config.MQTT_HOST)
    parser.add_argument("--broker-port", type=int, default=config.MQTT_PORT)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    floors = [args.floor] if args.floor else list(FLOORS.keys())

    t = MqttTransport(host=args.broker_host, port=args.broker_port, client_id="demo_events")
    t.connect()
    t.loop_start()
    time.sleep(0.3)

    print(f"▶ IF-05 {args.count}건 발행 시작 (층={floors}, 타입={args.types})")
    for i in range(1, args.count + 1):
        fl = random.choice(floors)
        f = FLOORS[fl]
        ev_type = random.choice(args.types)
        x = round(f["cx"] + random.uniform(-f["rx"], f["rx"]), 2)
        y = round(f["cy"] + random.uniform(-f["ry"], f["ry"]), 2)
        conf = round(random.uniform(0.70, 0.98), 2)
        msg = messages.if05(
            robot_id=f["robot_id"],
            event_type=ev_type,
            confidence=conf,
            location={"x": x, "y": y, "floor": fl},
            snapshot_ref=f"demo_{i:02d}.jpg",
        )
        t.publish(config.topic_event(f["robot_id"]), msg, config.QOS_EVENT)
        print(f"  [{i:02d}/{args.count}] {ev_type:<17} {f['robot_id']} "
              f"floor={fl} x={x} y={y} conf={conf}")
        time.sleep(args.interval)

    print("✅ 완료 — 2초 내 3D 뷰/이상감지 이력/관제 현황에 반영됩니다.")
    time.sleep(0.5)
    t.loop_stop()
    t.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
