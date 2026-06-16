#!/usr/bin/env python3
"""
FMS 설계 vs 실제 구현 아키텍처 비교 다이어그램 생성
출력: assets/arch_fms_planned.png, assets/arch_implemented.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe
from matplotlib.font_manager import FontProperties

KR   = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
KRB  = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')
MONO = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')

BG = '#0D1117'


def t(ax, x, y, text, fp=None, size=11, color='#FFFFFF',
      ha='center', va='center', zorder=5, bg=None):
    fp = fp or KR
    kw = dict(ha=ha, va=va, fontsize=size, color=color,
              fontproperties=fp, zorder=zorder)
    if bg:
        kw['path_effects'] = [pe.withStroke(linewidth=2.5, foreground=bg)]
    ax.text(x, y, text, **kw)


def box(ax, x, y, w, h, fc, ec='#556677', r=0.35, lw=2, alpha=1.0, zorder=2):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0,rounding_size={r}",
                       facecolor=fc, edgecolor=ec, linewidth=lw,
                       alpha=alpha, zorder=zorder)
    ax.add_patch(p)


def arr(ax, x1, y1, x2, y2, color, lw=2.2, rad=0.0, style='->'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                connectionstyle=f'arc3,rad={rad}',
                                shrinkA=6, shrinkB=6),
                zorder=6)


# ══════════════════════════════════════════════════════════════════════════════
# 다이어그램 1: 초기 FMS 설계 아키텍처 (폐기)
# ══════════════════════════════════════════════════════════════════════════════
def draw_fms_planned(path):
    fig, ax = plt.subplots(figsize=(18, 10))
    ax.set_xlim(0, 18); ax.set_ylim(0, 10)
    ax.axis('off')
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # 제목
    t(ax, 9, 9.6, '초기 설계 아키텍처 — FMS 서버 중심 (폐기)',
      fp=KRB, size=18, bg=BG)
    t(ax, 9, 9.15, 'MQTT 기반 중앙 집중형 · FMS가 Mission State 단독 소유',
      fp=KR, size=11, color='#778899', bg=BG)

    MQTT  = '#E09020'
    REST  = '#20B0D0'
    ALARM = '#DD4444'

    # ── 섹션 배경 ──────────────────────────────────────────────────────────────
    # 로봇 유닛 (좌)
    box(ax, 0.2, 1.0, 4.8, 7.6, '#0D1E30', ec='#1E4A7A', r=0.5, alpha=0.6, zorder=1)
    t(ax, 2.6, 8.38, '로봇 유닛 (TurtleBot4)', fp=KRB, size=11, color='#6699CC', bg=BG)

    # FMS 서버 (중앙)
    box(ax, 6.5, 2.5, 5.0, 5.5, '#1A1A0A', ec='#888833', r=0.5, alpha=0.7, zorder=1)
    t(ax, 9.0, 7.78, 'FMS 서버 (Flask + SQLite + MQTT)', fp=KRB, size=11, color='#CCCC44', bg=BG)

    # 외부 소비자 (우)
    box(ax, 13.0, 1.0, 4.8, 7.6, '#151022', ec='#3A1560', r=0.5, alpha=0.6, zorder=1)
    t(ax, 15.4, 8.38, '관제 / UI', fp=KRB, size=11, color='#9977BB', bg=BG)

    # ── 로봇 유닛 내부 ─────────────────────────────────────────────────────────
    box(ax, 0.5, 6.3, 4.2, 1.2, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 7.05, 'Interaction 트랙', fp=KRB, size=13)
    t(ax, 2.6, 6.65, '목적지 입력 · IF-01 요청 생성', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 4.7, 4.2, 1.2, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 5.45, 'Driving 트랙', fp=KRB, size=13)
    t(ax, 2.6, 5.05, 'task 수신 → Nav2 주행 실행', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 3.1, 4.2, 1.2, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 3.85, 'Vision 트랙', fp=KRB, size=13)
    t(ax, 2.6, 3.45, '이상감지 → IF-05 이벤트 발행', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 1.5, 4.2, 1.2, '#11192A', ec='#2A4060', r=0.3, zorder=3)
    t(ax, 2.6, 2.25, 'Bridge 노드 (로봇 측)', fp=KRB, size=11, color='#88BBDD')
    t(ax, 2.6, 1.85, 'ROS2 ↔ MQTT JSON 변환', fp=KR, size=9, color='#5577AA')

    # ── FMS 서버 내부 ──────────────────────────────────────────────────────────
    box(ax, 6.8, 6.3, 4.4, 1.1, '#3D3800', ec='#AAAA33', r=0.3, zorder=3)
    t(ax, 9.0, 7.0, 'mission_manager.py', fp=KRB, size=12, color='#EEEE88')
    t(ax, 9.0, 6.62, 'start/next 로봇 배정 · task 발행', fp=KR, size=8.5, color='#CCCC66')

    box(ax, 6.8, 4.85, 4.4, 1.1, '#3D3800', ec='#AAAA33', r=0.3, zorder=3)
    t(ax, 9.0, 5.55, 'state_machine.py', fp=KRB, size=12, color='#EEEE88')
    t(ax, 9.0, 5.17, 'Mission FSM · 전이표 기반 이벤트 구동', fp=KR, size=8.5, color='#CCCC66')

    box(ax, 6.8, 3.4, 4.4, 1.1, '#3D3800', ec='#AAAA33', r=0.3, zorder=3)
    t(ax, 9.0, 4.1, 'robot_registry.py', fp=KRB, size=12, color='#EEEE88')
    t(ax, 9.0, 3.72, 'Robot State 스냅샷 · 통신장애 감시', fp=KR, size=8.5, color='#CCCC66')

    box(ax, 6.8, 2.7, 2.0, 0.5, '#2A2A15', ec='#666633', r=0.2, zorder=3)
    t(ax, 7.8, 2.95, 'transport.py', fp=MONO, size=9, color='#AAAA55')
    box(ax, 9.2, 2.7, 2.0, 0.5, '#2A2A15', ec='#666633', r=0.2, zorder=3)
    t(ax, 10.2, 2.95, 'db.py (SQLite)', fp=MONO, size=9, color='#AAAA55')

    # ── 관제/UI ────────────────────────────────────────────────────────────────
    box(ax, 13.3, 6.3, 4.2, 1.2, '#3D1A72', ec='#8855CC', r=0.3, zorder=3)
    t(ax, 15.4, 7.05, '관제 대시보드', fp=KRB, size=13)
    t(ax, 15.4, 6.65, 'Flask GET API :5000', fp=KR, size=9, color='#BB99EE')

    box(ax, 13.3, 4.7, 4.2, 1.2, '#6B2010', ec='#CC6644', r=0.3, zorder=3)
    t(ax, 15.4, 5.45, 'Kiosk UI', fp=KRB, size=13)
    t(ax, 15.4, 5.05, 'Interaction 트랙 프론트엔드', fp=KR, size=9, color='#DDAA88')

    # ── MQTT 브로커 (중앙 하단) ────────────────────────────────────────────────
    box(ax, 6.8, 1.3, 4.4, 1.0, '#201010', ec='#884422', r=0.3, zorder=3)
    t(ax, 9.0, 1.95, 'Mosquitto MQTT Broker', fp=KRB, size=12, color='#EE9944')
    t(ax, 9.0, 1.55, 'localhost:1883  QoS 1', fp=MONO, size=9, color='#AA6622')

    # ── 화살표 ────────────────────────────────────────────────────────────────
    # 로봇 → MQTT (IF-01 요청, IF-02 상태, IF-05 이벤트)
    arr(ax, 4.7, 6.9, 6.8, 1.8, MQTT, lw=2.0, rad=-0.2)
    arr(ax, 4.7, 5.3, 6.8, 1.8, MQTT, lw=2.0, rad=-0.1)
    arr(ax, 4.7, 3.7, 6.8, 1.7, MQTT, lw=2.0, rad=0.0)
    t(ax, 5.7, 4.5, 'IF-01/02/05\nMQTT pub', fp=MONO, size=8, color=MQTT, bg=BG)

    # MQTT → FMS
    arr(ax, 9.0, 2.3, 9.0, 3.4, MQTT, lw=2.5)
    t(ax, 9.8, 2.8, 'subscribe', fp=MONO, size=8, color=MQTT, bg=BG)

    # FMS → MQTT (IF-03 task)
    arr(ax, 7.5, 2.7, 6.5, 2.0, MQTT, lw=2.0, rad=0.1, style='<-')
    t(ax, 6.3, 2.5, 'IF-03\ntask pub', fp=MONO, size=8, color=MQTT, bg=BG)

    # MQTT → 로봇 (task 수신)
    arr(ax, 6.8, 1.5, 4.7, 5.0, MQTT, lw=2.0, rad=0.15, style='<-')

    # FMS → 관제 (REST)
    arr(ax, 11.2, 6.8, 13.3, 6.9, REST, lw=2.2)
    t(ax, 12.2, 7.1, 'GET API', fp=MONO, size=8, color=REST, bg=BG)

    # IF-05 이벤트 → 관제 알람
    arr(ax, 4.7, 3.5, 13.3, 4.9, ALARM, lw=1.8, rad=-0.15)
    t(ax, 9.0, 3.0, 'IF-05 이벤트 알람', fp=KR, size=8.5, color=ALARM, bg=BG)

    # ── 범례 ──────────────────────────────────────────────────────────────────
    box(ax, 0.3, 0.1, 17.4, 0.8, '#111820', ec='#334455', r=0.2, zorder=4)
    items = [
        (MQTT,  'MQTT 메시지 (QoS 1)'),
        (REST,  'REST API (HTTP GET)'),
        (ALARM, 'IF-05 이벤트 알람'),
        ('#CCCC44', 'FMS 내부 모듈'),
    ]
    for i, (c, label) in enumerate(items):
        xi = 1.2 + i * 4.2
        yi = 0.5
        ax.plot([xi, xi + 0.45], [yi, yi], color=c, lw=2.5, zorder=7)
        ax.annotate('', xy=(xi + 0.45, yi), xytext=(xi + 0.3, yi),
                    arrowprops=dict(arrowstyle='->', color=c, lw=2), zorder=7)
        t(ax, xi + 0.6, yi, label, fp=KR, size=9, color='#AABBCC', ha='left', bg=BG)

    plt.savefig(path, dpi=180, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'saved → {path}')


# ══════════════════════════════════════════════════════════════════════════════
# 다이어그램 2: 실제 구현 아키텍처
# ══════════════════════════════════════════════════════════════════════════════
def draw_implemented(path):
    fig, ax = plt.subplots(figsize=(18, 10))
    ax.set_xlim(0, 18); ax.set_ylim(0, 10)
    ax.axis('off')
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # 제목
    t(ax, 9, 9.6, '실제 구현 아키텍처 — ROS2 토픽 + Bridge 노드 집계',
      fp=KRB, size=18, bg=BG)
    t(ax, 9, 9.15, 'FMS 서버 없음 · escort_state_bridge_node가 상태 단독 집계',
      fp=KR, size=11, color='#778899', bg=BG)

    ROS  = '#E09020'
    DATA = '#40C070'
    WS   = '#20B0D0'
    HTTP = '#9966DD'

    # ── 섹션 배경 ──────────────────────────────────────────────────────────────
    box(ax, 0.2, 1.0, 4.8, 7.6, '#0D1E30', ec='#1E4A7A', r=0.5, alpha=0.6, zorder=1)
    t(ax, 2.6, 8.38, '로봇 유닛 (TurtleBot4)', fp=KRB, size=11, color='#6699CC', bg=BG)

    box(ax, 5.5, 1.0, 7.2, 7.6, '#0D2318', ec='#1A5030', r=0.5, alpha=0.6, zorder=1)
    t(ax, 9.1, 8.38, 'alfred_bridge (관리자 PC)', fp=KRB, size=11, color='#66BB88', bg=BG)

    box(ax, 13.2, 1.0, 4.6, 7.6, '#151022', ec='#3A1560', r=0.5, alpha=0.6, zorder=1)
    t(ax, 15.5, 8.38, '관제 / UI', fp=KRB, size=11, color='#9977BB', bg=BG)

    # ── 로봇 유닛 내부 ─────────────────────────────────────────────────────────
    box(ax, 0.5, 6.5, 4.2, 1.1, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 7.2, 'patrol_node / navigation_node', fp=KRB, size=11)
    t(ax, 2.6, 6.82, '순찰 · 에스코트 · Nav2 주행', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 5.1, 4.2, 1.1, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 5.8, 'scenario_manager_node', fp=KRB, size=12)
    t(ax, 2.6, 5.42, '릴레이 에스코트 시나리오 실행', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 3.7, 4.2, 1.1, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 4.4, 'detector_node', fp=KRB, size=12)
    t(ax, 2.6, 4.02, 'YOLO 이상감지 → detection/info', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 2.3, 4.2, 1.1, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
    t(ax, 2.6, 3.0, 'Interaction (Kiosk UI)', fp=KRB, size=12)
    t(ax, 2.6, 2.62, 'rosbridge :9090 → /information', fp=KR, size=9, color='#99BBCC')

    box(ax, 0.5, 1.1, 4.2, 0.9, '#11192A', ec='#2A4060', r=0.3, zorder=3)
    t(ax, 2.6, 1.7, 'Nav2 + AMCL (TurtleBot4)', fp=KRB, size=11, color='#88BBDD')
    t(ax, 2.6, 1.35, '위치 추정 · 자율주행', fp=KR, size=8.5, color='#5577AA')

    # ── alfred_bridge 노드 ─────────────────────────────────────────────────────
    box(ax, 5.8, 6.3, 6.6, 1.3, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
    t(ax, 9.1, 7.1, 'escort_state_bridge_node', fp=KRB, size=13)
    t(ax, 9.1, 6.72, '토픽 집계 → 에스코트 FSM → /escort_state, /{robot}/ui_state', fp=KR, size=8.5, color='#88CCAA')

    box(ax, 5.8, 4.7, 6.6, 1.3, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
    t(ax, 9.1, 5.5, 'robot_state_publisher_node', fp=KRB, size=13)
    t(ax, 9.1, 5.12, 'AMCL 위치 + 배터리 → /{robot}/robot_state (1Hz)', fp=KR, size=8.5, color='#88CCAA')

    box(ax, 5.8, 3.1, 6.6, 1.3, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
    t(ax, 9.1, 3.9, 'state_ws_bridge_node', fp=KRB, size=13)
    t(ax, 9.1, 3.52, '상태 변화 감지 → WebSocket broadcast :9091', fp=KR, size=8.5, color='#88CCAA')

    box(ax, 5.8, 1.5, 6.6, 1.3, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
    t(ax, 9.1, 2.3, 'rosbridge_server', fp=KRB, size=13)
    t(ax, 9.1, 1.92, 'Kiosk ↔ ROS2 토픽 WebSocket 게이트웨이 :9090', fp=KR, size=8.5, color='#88CCAA')

    # ── 관제/UI ────────────────────────────────────────────────────────────────
    box(ax, 13.5, 6.3, 3.9, 1.3, '#3D1A72', ec='#8855CC', r=0.3, zorder=3)
    t(ax, 15.45, 7.1, 'monitor_server', fp=KRB, size=13)
    t(ax, 15.45, 6.72, 'Flask :5000 · 대시보드 REST API', fp=KR, size=9, color='#BB99EE')

    box(ax, 13.5, 4.7, 3.9, 1.3, '#6B2010', ec='#CC6644', r=0.3, zorder=3)
    t(ax, 15.45, 5.5, 'Kiosk UI (React)', fp=KRB, size=13)
    t(ax, 15.45, 5.12, 'alfred_interaction · WebSocket 수신', fp=KR, size=9, color='#DDAA88')

    box(ax, 13.5, 3.1, 3.9, 1.3, '#222233', ec='#445566', r=0.3, zorder=3)
    t(ax, 15.45, 3.9, '관제 대시보드 (Web)', fp=KRB, size=12)
    t(ax, 15.45, 3.52, 'WebSocket :9091 실시간 상태 수신', fp=KR, size=9, color='#8899AA')

    # ── 화살표 ────────────────────────────────────────────────────────────────
    # patrol/scenario → escort_state_bridge (nav_status)
    arr(ax, 4.7, 7.05, 5.8, 7.05, ROS)
    arr(ax, 4.7, 5.65, 5.8, 6.8, ROS, rad=0.1)
    t(ax, 5.4, 7.25, '/{robot}/nav_status', fp=MONO, size=7.5, color=ROS, bg=BG)

    # detector → escort_state_bridge (detection)
    arr(ax, 4.7, 4.25, 5.8, 6.6, ROS, lw=1.8, rad=0.2)
    t(ax, 4.5, 5.6, '/{ns}/detection/info', fp=MONO, size=7.5, color=ROS, bg=BG, ha='right')

    # Nav2/AMCL → robot_state_publisher
    arr(ax, 4.7, 1.55, 5.8, 5.1, DATA, lw=1.8, rad=0.15)
    t(ax, 4.5, 3.2, 'amcl_pose\nbattery_state', fp=MONO, size=7.5, color=DATA, bg=BG, ha='right')

    # escort_state_bridge → state_ws_bridge
    arr(ax, 9.1, 6.3, 9.1, 4.4, DATA, lw=2.2)
    t(ax, 9.9, 5.4, '/escort_state', fp=MONO, size=8, color=DATA, bg=BG)

    # robot_state_publisher → monitor_server
    arr(ax, 12.4, 5.2, 13.5, 6.8, DATA, lw=2.2)
    t(ax, 13.3, 6.1, '/{robot}/robot_state', fp=MONO, size=7.5, color=DATA, bg=BG, ha='right')

    # state_ws_bridge → 관제 대시보드
    arr(ax, 12.4, 3.7, 13.5, 3.7, WS, lw=2.2)
    t(ax, 12.9, 3.95, 'WebSocket', fp=MONO, size=8, color=WS, bg=BG)

    # state_ws_bridge → Kiosk UI (ui_state)
    arr(ax, 12.4, 3.5, 13.5, 5.05, WS, lw=2.0, rad=-0.15)
    t(ax, 13.2, 4.15, '/{robot}/ui_state', fp=MONO, size=7.5, color=WS, bg=BG, ha='right')

    # Kiosk → rosbridge
    arr(ax, 13.5, 5.0, 12.4, 2.05, WS, lw=1.8, rad=0.2, style='<-')
    t(ax, 13.6, 3.4, 'WebSocket\n/information', fp=MONO, size=7.5, color=WS, bg=BG, ha='left')

    # rosbridge → scenario_manager
    arr(ax, 5.8, 1.95, 4.7, 5.5, ROS, lw=1.8, rad=-0.15, style='<-')
    t(ax, 4.5, 3.8, '/information\n→/scenario_request', fp=MONO, size=7.5, color=ROS, bg=BG, ha='right')

    # monitor_server → 관제 대시보드 (REST)
    arr(ax, 15.45, 6.3, 15.45, 4.4, HTTP, lw=1.8)
    t(ax, 16.0, 5.35, 'GET API', fp=MONO, size=8, color=HTTP, bg=BG, ha='left')

    # ── 범례 ──────────────────────────────────────────────────────────────────
    box(ax, 0.3, 0.1, 17.4, 0.8, '#111820', ec='#334455', r=0.2, zorder=4)
    items = [
        (ROS,  'ROS2 토픽 (DDS)'),
        (DATA, 'RobotState 집계 메시지'),
        (WS,   'WebSocket push/sub'),
        (HTTP, 'REST API (HTTP)'),
    ]
    for i, (c, label) in enumerate(items):
        xi = 1.5 + i * 4.0
        yi = 0.5
        ax.plot([xi, xi + 0.45], [yi, yi], color=c, lw=2.5, zorder=7)
        ax.annotate('', xy=(xi + 0.45, yi), xytext=(xi + 0.3, yi),
                    arrowprops=dict(arrowstyle='->', color=c, lw=2), zorder=7)
        t(ax, xi + 0.6, yi, label, fp=KR, size=9, color='#AABBCC', ha='left', bg=BG)

    plt.savefig(path, dpi=180, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'saved → {path}')


if __name__ == '__main__':
    draw_fms_planned('/home/junsu/Project_Rokey_turtlebot4/assets/arch_fms_planned.png')
    draw_implemented('/home/junsu/Project_Rokey_turtlebot4/assets/arch_implemented.png')
    print('완료')
