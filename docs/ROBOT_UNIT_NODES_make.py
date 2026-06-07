"""로봇 유닛 노드 구성도 생성기 — 반듯한 박스 그리드(matplotlib).

실행: python3 docs/ROBOT_UNIT_NODES_make.py
출력: docs/ROBOT_UNIT_NODES.png, .svg
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib import font_manager as fm

REG = fm.FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
BLD = fm.FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")

# 색
PUR, PURf = "#6a5acd", "#e7e4f7"
RED, REDf = "#c0504d", "#f7e4e1"
GRN, GRNf = "#3f8a55", "#e3f2e6"
BLU, BLUf = "#4a6fa5", "#dce8f7"
VIO, VIOf = "#7a4ea5", "#ece3f2"
GRY, GRYf = "#888888", "#f3f3f3"
ORG, ORGf = "#c08a4a", "#fdf0e0"
YEL, YELf = "#a58b4a", "#f8f1d2"
GBUS = "#f4f4f4"

fig, ax = plt.subplots(figsize=(20, 12.6), dpi=150)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")


def box(x, y, w, h, face, edge, lw=1.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.8",
                                fc=face, ec=edge, lw=lw, mutation_aspect=0.6))


def card(x, y, w, h, title, lines, face, edge, lw=1.3, star=False):
    box(x, y, w, h, face, edge, lw)
    t = title + ("   ★" if star else "")
    ax.text(x + 0.7, y + h - 1.5, t, fontproperties=BLD, fontsize=10.5, va="top", ha="left", color="#1a1a1a")
    for i, ln in enumerate(lines):
        col = "#222222"
        if ln.startswith("▼"):
            col = "#3a3a8a"
        elif ln.startswith("▲"):
            col = "#8a3a3a"
        ax.text(x + 0.7, y + h - 3.6 - i * 1.85, ln, fontproperties=REG, fontsize=8.0,
                va="top", ha="left", color=col)


def simplebox(x, y, w, h, title, sub, face, edge):
    box(x, y, w, h, face, edge, 1.3)
    ax.text(x + w / 2, y + h - 1.7, title, fontproperties=BLD, fontsize=9.5, va="top", ha="center")
    if sub:
        ax.text(x + w / 2, y + h - 3.7, sub, fontproperties=REG, fontsize=7.6, va="top", ha="center", color="#555")


def band_label(y, txt, color):
    ax.text(0.3, y, txt, fontproperties=BLD, fontsize=10, va="center", ha="left", color=color)


def arrow(p0, p1, color, ls="-", lw=1.6, label=None, lpos=0.5, both=False):
    style = "<|-|>" if both else "-|>"
    ax.annotate("", xy=p1, xytext=p0,
                arrowprops=dict(arrowstyle=style, color=color, linestyle=ls, lw=lw,
                                shrinkA=3, shrinkB=3, mutation_scale=13))
    if label:
        mx = p0[0] + (p1[0] - p0[0]) * lpos
        my = p0[1] + (p1[1] - p0[1]) * lpos
        ax.text(mx, my, label, fontproperties=BLD, fontsize=7.6, color=color, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=0.6))


# ── 제목 ──
ax.text(50, 98.3, "에스코트 로봇 유닛 — ROS2 노드 구성 (참조 제안)", fontproperties=BLD, fontsize=19, ha="center")
ax.text(50, 95.3, "robot2 기준 · 브리지가 ROS↔IF 양방향 번역 · FMS는 IF-01/02/03/05만 인지(ROS 비의존)",
        fontproperties=REG, fontsize=11, ha="center", color="#555")

# ════════ 하드웨어 행 (y 86~93) ════════
band_label(89.5, "하드웨어", GRY)
simplebox(8,  86, 13, 7, "마이크", "음성 입력", GRYf, GRY)
simplebox(73, 86, 24, 7, "카메라 OAK-D", "RGB · 깊이", GRYf, GRY)
simplebox(48, 86, 11, 7, "2D LiDAR", "", GRYf, GRY)
simplebox(60, 86, 11, 7, "Create3", "베이스", GRYf, GRY)
simplebox(2,  86, 5,  7, "터치", "스크린", GRYf, GRY)

# ════════ 외부 행 (y 74~81) ════════
band_label(77.5, "외부\n(유닛 밖)", ORG)
simplebox(8,  74, 28, 7, "STT/LLM/TTS 서비스", "로컬망 / 클라우드", ORGf, ORG)
simplebox(40, 74, 24, 7, "관리자 UI", "영상 시청(브라우저)", YELf, YEL)
simplebox(73, 74, 24, 7, "FMS 호스트 PC", "MQTT broker :1883", BLUf, BLU)

# ════════ 메인 노드 (y 31~70) ════════
band_label(63, "노드", "#444")
# col1 — Interaction A
card(2, 52, 21, 16, "ui_node", ["터치스크린·얼굴·Q·A", "▼ /robot2/robot_state", "▲ /robot2/ui/request →IF-01",
                                 "   /interaction/call"], PURf, PUR)
card(2, 31, 21, 17, "stt_node", ["음성 → 텍스트", "▼ 마이크 audio", "▲ /interaction/stt_text"], PURf, PUR)
# col2 — Interaction B
card(25, 52, 21, 16, "llm_node", ["목적지 정규화·대화", "▼ /interaction/stt_text", "▲ /interaction/destination",
                                  "   /interaction/dialog"], PURf, PUR)
card(25, 31, 21, 17, "tts_node", ["텍스트 → 음성", "▼ /interaction/dialog", "▲ 스피커 audio"], PURf, PUR)
# col3 — Driving
card(48, 40, 24, 28, "behavior_node", ["Robot State 단독 소유", "▼ /robot2/fms/task ←IF-03",
                                       "   /interaction/call · /safety/estop", "▲ /robot2/robot_state →IF-02",
                                       "   /robot2/fms/task_ack", "   nav2 goal",
                                       "PATROL→…→RETURNING 전이", "task 없으면 자율 PATROL"],
     REDf, RED, lw=2.0, star=True)
card(48, 31, 11.5, 7.5, "nav2 스택", ["▼ goal·/scan", "▲ /cmd_vel"], REDf, RED)
card(60.5, 31, 11.5, 7.5, "localization", ["AMCL+ArUco", "▲ /tf·pose"], REDf, RED)
# col4 — Vision / Video
card(74, 52, 23, 16, "yolo_monitor_node", ["이상감지(순찰 중)", "▼ /camera/image",
                                           "▲ /robot2/vision/alert →IF-05", "FIRE / SUSPICIOUS_PERSON"], GRNf, GRN)
card(74, 31, 23, 17, "video_sender_node", ["(향후·선택)", "▼ /camera/image",
                                           "→ WebRTC 관리자 UI 직접", "(데이터평면, FMS 우회)"], VIOf, VIO)

# ════════ 브리지 (y 20~28) ════════
box(2, 20, 95, 8.2, BLUf, BLU, 2.0)
ax.text(3, 27.0, "fms_bridge_node   (ROS ↔ IF/MQTT 양방향 번역, 유닛당 1개 · 유일 MQTT 창구)",
        fontproperties=BLD, fontsize=11, va="top", ha="left")
ax.text(3, 24.4, "▼ subs(ROS)  /robot2/robot_state · /robot2/ui/request · /robot2/vision/alert · /robot2/fms/task_ack",
        fontproperties=REG, fontsize=8.4, va="top", ha="left", color="#3a3a8a")
ax.text(3, 22.6, "▲ pubs(ROS)  /robot2/fms/task (IF-03 수신→재발행)      "
        "MQTT  robot/robot2/status·request·event·task·task_ack ↔ FMS",
        fontproperties=REG, fontsize=8.4, va="top", ha="left", color="#8a3a3a")

# ════════ 토픽 버스 (y 10~17.5) ════════
box(2, 10, 95, 7.5, GBUS, GRY, 1.3)
ax.text(50, 16.6, "ROS2 토픽 버스 (유닛 내부 · robot2 네임스페이스)", fontproperties=BLD, fontsize=9.5, va="top", ha="center")
ax.text(50, 14.2, "/robot2/robot_state · /robot2/ui/request · /robot2/fms/task · /robot2/fms/task_ack · "
        "/robot2/vision/alert · /robot2/pose", fontproperties=REG, fontsize=8.2, va="top", ha="center", color="#333")
ax.text(50, 12.4, "/interaction/stt_text · /interaction/destination · /interaction/dialog · /interaction/call · "
        "/scan · /odom · /tf · /cmd_vel · /camera/image · /safety/estop",
        fontproperties=REG, fontsize=8.2, va="top", ha="center", color="#333")

# ════════ 범례 (y 1~8.5) ════════
box(2, 1, 95, 7.6, YELf, YEL, 1.3)
ax.text(3, 7.8, "범례", fontproperties=BLD, fontsize=10, va="top", ha="left")
leg1 = [("■ Interaction", PUR), ("  ■ Driving(behavior★·nav2·loc)", RED),
        ("  ■ Vision", GRN), ("  ■ 경계 bridge", BLU), ("  ■ 데이터평면 video", VIO)]
xx = 3
for txt, c in leg1:
    ax.text(xx, 5.7, txt, fontproperties=BLD, fontsize=8.6, va="top", ha="left", color=c)
    xx += len(txt) * 0.95 + 1.5
leg2 = [("┄ ROS2 토픽(보고)", GRN), ("  ━ 명령 IF-03(FMS→로봇)", "#1f3d7a"),
        ("  ━ MQTT IF(제어평면)", RED), ("  ━ WebRTC 영상", VIO), ("  ┄ 외부 AI", ORG)]
xx = 3
for txt, c in leg2:
    ax.text(xx, 3.9, txt, fontproperties=BLD, fontsize=8.6, va="top", ha="left", color=c)
    xx += len(txt) * 0.95 + 1.5
ax.text(3, 2.2, "방향: 로봇이 FMS에 보고(IF-01/02/05·ack) ↑ · FMS가 로봇에 내리는 명령은 IF-03 task ↓ 뿐 "
        "(bridge→behavior_node 수신→Nav2 수행).  ★ Robot State는 behavior_node 단독 소유.",
        fontproperties=REG, fontsize=8.2, va="top", ha="left", color="#444")

# ════════ 연결선 ════════
# ROS2(초록 점선)
arrow((8 + 6.5, 86), (12.5, 48), GRN, ls=(0, (5, 3)), lw=1.4, label="audio")          # mic→stt (approx)
arrow((73, 89.5), (85, 68), GRN, ls=(0, (5, 3)), lw=1.4)                                # oakd→yolo
arrow((75, 86), (85, 48), VIO, ls=(0, (5, 3)), lw=1.4)                                  # oakd→video
arrow((53.5, 86), (53.5, 38.5), GRN, ls=(0, (5, 3)), lw=1.2)                            # lidar→nav2
arrow((4.5, 86), (12.5, 68), GRN, ls=(0, (5, 3)), lw=1.2)                               # touch→ui
arrow((12.5, 52), (12.5, 48), GRN, ls=(0, (5, 3)), lw=1.2)                              # ui↔stt(col)
arrow((23, 60), (25, 60), GRN, ls=(0, (5, 3)), lw=1.2, label="/stt_text")              # stt→llm (row)
arrow((25, 62), (23, 62), GRN, ls=(0, (5, 3)), lw=1.2)                                  # llm→ui
arrow((60, 50), (60, 39), GRN, ls=(0, (5, 3)), lw=1.2, label="goal")                   # behavior→nav2

# 보고 IF 원천 → 브리지 (초록, 로봇→FMS 방향)
arrow((12.5, 52), (20, 28.2), GRN, ls=(0, (5, 3)), lw=1.6, label="IF-01")              # ui→bridge
arrow((60, 40), (55, 28.2), GRN, ls=(0, (5, 3)), lw=1.6, label="IF-02·ack")            # behavior→bridge
arrow((85, 52), (80, 28.2), GRN, ls=(0, (5, 3)), lw=1.6, label="IF-05")                # yolo→bridge

# ★ 명령(FMS→로봇): bridge → behavior_node (IF-03 task) — 굵은 남색 실선으로 강조
arrow((45, 26), (52, 40), "#1f3d7a", ls="-", lw=2.6, label="명령 IF-03 task")          # bridge→behavior

# 제어평면 MQTT (빨강) bridge↔FMS — 보고(↑) + 명령(↓) 방향 명시
arrow((87, 28.2), (85, 74), RED, lw=2.4, both=True,
      label="↑ 보고 IF-01/02/05·ack    ↓ 명령 IF-03", lpos=0.5)

# 데이터평면 (보라) video→adminui
arrow((85, 48), (55, 74), VIO, lw=2.2, label="영상 WebRTC", lpos=0.5)

# 외부 AI (주황 점선)
arrow((14, 48), (16, 74), ORG, ls=":", lw=1.4)                                         # stt↔aisvc
arrow((30, 68), (24, 74), ORG, ls=":", lw=1.4)                                         # llm↔aisvc

plt.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)
fig.savefig("/home/sungyu/alfred_ws/docs/ROBOT_UNIT_NODES.png", dpi=150)
fig.savefig("/home/sungyu/alfred_ws/docs/ROBOT_UNIT_NODES.svg")
print("saved ROBOT_UNIT_NODES.png / .svg")
