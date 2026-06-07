"""FMS 실시간 대시보드 — 조회 API를 폴링해 로봇/미션 상태를 라이브로 보여준다.

서버 동작을 '눈으로' 보기 위한 도구. 미션을 돌리는 동안 상태·전이가 실시간으로 바뀐다.

실행:
    python3 tools/watch.py                 # 0.5초마다 갱신(라이브)
    python3 tools/watch.py --once          # 한 프레임만 출력(비TTY/캡처용)
    python3 tools/watch.py --interval 1.0  # 갱신 주기 변경

미션을 일으키려면 다른 터미널에서:
    python3 tools/send_request.py --robot-id robot2 --dest GATE_30 --dest-floor 2
    python3 tools/send_event.py   --robot-id robot2 --type FIRE
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone


# ── ANSI ─────────────────────────────────────────────────────────────────
RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
GRAY = "\033[90m"; RED = "\033[91m"; GREEN = "\033[92m"
YEL = "\033[93m"; BLUE = "\033[94m"; CYAN = "\033[96m"
CLEAR = "\033[H\033[J"

ROBOT_COLOR = {
    "PATROL": GRAY, "IDLE": GRAY,
    "INTERACTING": CYAN, "RESERVED": YEL, "HANDOVER_READY": YEL,
    "WAITING_HANDOVER": YEL, "ESCORTING": GREEN, "RETURNING": BLUE,
    "EMERGENCY": RED + BOLD, "ERROR": RED + BOLD,
}
MISSION_COLOR = {
    "REQUESTED": CYAN, "ASSIGNED": CYAN,
    "ESCORTING_TO_HANDOVER": YEL, "HANDOVER_WAITING": YEL + BOLD,
    "ESCORTING_TO_FINAL": GREEN, "COMPLETED": GREEN + BOLD,
    "CANCELLED": RED, "EMERGENCY": RED + BOLD, "FAILED": RED,
}


USE_COLOR = sys.stdout.isatty()  # 파이프/캡처 시 색 자동 비활성


def color(text, c):
    if not USE_COLOR:
        return str(text)
    return f"{c}{text}{RESET}"


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=2) as r:
        return json.loads(r.read())


def age(last_seen, timeout):
    try:
        secs = (datetime.now(timezone.utc) - datetime.fromisoformat(last_seen)).total_seconds()
    except (ValueError, TypeError):
        return "?"
    txt = f"{secs:.1f}s"
    return color(txt + " STALE", RED) if secs > timeout else color(txt, GRAY)


def render(base, timeout) -> str:
    out = []
    bar = "═" * 64
    out.append(color(f"╔{bar}╗", DIM))
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    title = f"  FMS 실시간 대시보드           {now} (UTC)"
    out.append(color("║", DIM) + color(title.ljust(64), BOLD) + color("║", DIM))
    out.append(color(f"╚{bar}╝", DIM))

    try:
        robots = get(base, "/api/robots")
        missions = get(base, "/api/missions")
        events = get(base, "/api/events?limit=3")
    except Exception:
        out.append("")
        out.append(color("  ⚠ FMS 연결 안됨 — main.py 기동 여부/포트 확인", RED))
        out.append(color(f"    ({base}/api/robots)", DIM))
        return "\n".join(out)

    # ── 로봇 ──────────────────────────────────────────────────────────────
    out.append("")
    out.append(color("  로봇 (IF-02 관측)", BOLD))
    out.append(color("  ┌──────────┬───────────────────┬──────────────────────┬──────────┐", DIM))
    out.append(color("  │ robot_id │ Robot State       │ current task         │ battery  │", DIM))
    out.append(color("  ├──────────┼───────────────────┼──────────────────────┼──────────┤", DIM))
    for r in robots:
        st = r.get("state") or "-"
        stc = color(st.ljust(17), ROBOT_COLOR.get(st, ""))
        task = r.get("current_task_id")
        # task_id는 길어서 task 종류 대신 id 끝부분 표시; null이면 (순찰/대기)
        task_disp = "(순찰/대기)" if not task else "…" + str(task)[-18:]
        batt = r.get("battery")
        batt_disp = f"{batt}%" if batt is not None else "-"
        seen = age(r.get("last_seen"), timeout)
        out.append(f"  │ {r['robot_id']:<8} │ {stc} │ {task_disp:<20} │ {batt_disp:<8} │  {seen}")
    out.append(color("  └──────────┴───────────────────┴──────────────────────┴──────────┘", DIM))

    # ── 활성 미션 ─────────────────────────────────────────────────────────
    out.append("")
    out.append(color("  활성 미션 (Mission State — FMS 단독 소유)", BOLD))
    active = missions.get("active", [])
    if not active:
        out.append(color("    대기 중 — 활성 미션 없음. (다른 터미널에서 send_request.py 실행)", DIM))
    else:
        m = active[0]
        try:
            detail = get(base, f"/api/missions/{m['mission_id']}")
        except Exception:
            detail = m
        ms = m.get("state")
        out.append(f"    {color(m['mission_id'], DIM)}   "
                   f"{color(ms, MISSION_COLOR.get(ms, BOLD))}   "
                   f"start={color(m.get('start_robot'), BOLD)} next={m.get('next_robot')}")
        lat = m.get("handover_latency_ms")
        lat_disp = (color(f"{lat} ms", GREEN if (lat or 0) <= 3000 else RED)
                    if lat is not None else color("측정 전", DIM))
        out.append(f"    핸드오버 지연: {lat_disp}  (목표 ≤ 3000 ms)")
        trail = " → ".join(t["to_state"] for t in detail.get("transitions", []))
        out.append(f"    전이: {color(trail, CYAN)}")

    # ── 최근 종료 미션 (완료 후에도 핸드오버 지연 결과를 남겨 보여줌) ───────
    terminal = {"COMPLETED", "CANCELLED", "EMERGENCY", "FAILED"}
    finished = [x for x in missions.get("missions", []) if x.get("state") in terminal]
    if finished:
        fm = finished[0]
        lat = fm.get("handover_latency_ms")
        lat_disp = (color(f"{lat}ms", GREEN if (lat or 0) <= 3000 else RED)
                    if lat is not None else color("—", DIM))
        out.append(f"    {color('최근 종료:', DIM)} {fm['mission_id']}  "
                   f"{color(fm['state'], MISSION_COLOR.get(fm['state'], ''))}  핸드오버 {lat_disp}")

    # ── 최근 이상감지 ─────────────────────────────────────────────────────
    out.append("")
    out.append(color("  최근 이상감지 (IF-05)", BOLD))
    if not events:
        out.append(color("    없음", DIM))
    for e in events:
        out.append(f"    {color('[' + str(e.get('event_type')) + ']', RED)} "
                   f"{e.get('robot_id')}  conf={e.get('confidence')} floor={e.get('floor')}")

    out.append("")
    out.append(color("  Ctrl+C 종료 │ 미션: send_request.py │ 이상감지: send_event.py", DIM))
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description="FMS 실시간 대시보드")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--timeout", type=float, default=10.0, help="STALE 표시 임계(초)")
    p.add_argument("--once", action="store_true", help="한 프레임만 출력")
    args = p.parse_args()
    base = f"http://{args.host}:{args.port}"

    if args.once:
        print(render(base, args.timeout))
        return 0

    try:
        while True:
            frame = render(base, args.timeout)
            sys.stdout.write(CLEAR + frame + "\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
