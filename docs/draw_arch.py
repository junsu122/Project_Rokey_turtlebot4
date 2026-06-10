#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe
from matplotlib.font_manager import FontProperties

KR  = FontProperties(fname='/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf')
KRB = FontProperties(fname='/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf')
MONO= FontProperties(fname='/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf')

def t(ax, x, y, text, fp=None, size=11, color='#FFFFFF',
      ha='center', va='center', zorder=5, bg=None):
    fp = fp or KR
    kw = dict(ha=ha, va=va, fontsize=size, color=color,
              fontproperties=fp, zorder=zorder)
    if bg:
        kw['path_effects'] = [pe.withStroke(linewidth=2.5, foreground=bg)]
    ax.text(x, y, text, **kw)

def box(ax, x, y, w, h, fc, ec='#556677', r=0.4, lw=2, alpha=1.0, zorder=2):
    p = FancyBboxPatch((x,y), w, h,
                       boxstyle=f"round,pad=0,rounding_size={r}",
                       facecolor=fc, edgecolor=ec, linewidth=lw,
                       alpha=alpha, zorder=zorder)
    ax.add_patch(p)

def arr(ax, x1, y1, x2, y2, color, lw=2.2, rad=0.0):
    ax.annotate('', xy=(x2,y2), xytext=(x1,y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                connectionstyle=f'arc3,rad={rad}',
                                shrinkA=6, shrinkB=6),
                zorder=6)

BG = '#0D1117'
fig, ax = plt.subplots(figsize=(18, 10))
ax.set_xlim(0, 18); ax.set_ylim(0, 10)
ax.axis('off')
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

# ── 제목 ──────────────────────────────────────────────────────────────────────
t(ax, 9, 9.6, 'alfred_bridge  코드 아키텍처', fp=KRB, size=20, bg=BG)
t(ax, 9, 9.15, 'ROS2 토픽 → 상태 변환 → WebSocket / Monitor Server 전달',
  fp=KR, size=11, color='#778899', bg=BG)

# ── 섹션 배경 ─────────────────────────────────────────────────────────────────
box(ax, 0.2, 1.0, 4.8, 7.6, '#0D1E30', ec='#1E4A7A', r=0.5, alpha=0.6, zorder=1)
box(ax, 5.5, 1.0, 7.2, 7.6, '#0D2318', ec='#1A5030', r=0.5, alpha=0.6, zorder=1)
box(ax, 13.2,1.0, 4.6, 7.6, '#151022', ec='#3A1560', r=0.5, alpha=0.6, zorder=1)

t(ax, 2.6,  8.38, 'alfred_driving', fp=KRB, size=11, color='#6699CC', bg=BG)
t(ax, 9.1,  8.38, 'alfred_bridge',  fp=KRB, size=11, color='#66BB88', bg=BG)
t(ax, 15.5, 8.38, '외부 소비자',    fp=KRB, size=11, color='#9977BB', bg=BG)

# ── alfred_driving 노드 2개 ───────────────────────────────────────────────────
box(ax, 0.5, 6.3, 4.2, 1.2, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
t(ax, 2.6, 7.05, 'patrol_node', fp=KRB, size=13)
t(ax, 2.6, 6.65, '(robot2 순찰 · 배터리)', fp=KR, size=9, color='#99BBCC')

box(ax, 0.5, 4.7, 4.2, 1.2, '#1B4F8A', ec='#4488CC', r=0.3, zorder=3)
t(ax, 2.6, 5.45, 'web_request_node', fp=KRB, size=13)
t(ax, 2.6, 5.05, '(웹 STOP / ESCORT 처리)', fp=KR, size=9, color='#99BBCC')

# ── alfred_bridge 노드 3개 ────────────────────────────────────────────────────
box(ax, 5.8, 6.3, 6.6, 1.2, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
t(ax, 9.1, 7.05, 'escort_state_bridge_node', fp=KRB, size=13)
t(ax, 9.1, 6.65, '에스코트 단계 상태머신', fp=KR, size=9, color='#88CCAA')

box(ax, 5.8, 4.7, 6.6, 1.2, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
t(ax, 9.1, 5.45, 'robot_state_publisher_node', fp=KRB, size=13)
t(ax, 9.1, 5.05, '위치 · 배터리 → RobotState 1Hz 발행', fp=KR, size=9, color='#88CCAA')

box(ax, 5.8, 3.1, 6.6, 1.2, '#1A5C38', ec='#44AA66', r=0.3, zorder=3)
t(ax, 9.1, 3.85, 'state_ws_bridge_node', fp=KRB, size=13)
t(ax, 9.1, 3.45, 'ROS 토픽 → WebSocket :9091 push', fp=KR, size=9, color='#88CCAA')

# ── 외부 소비자 3개 ───────────────────────────────────────────────────────────
box(ax, 13.5, 6.3, 3.9, 1.2, '#3D1A72', ec='#8855CC', r=0.3, zorder=3)
t(ax, 15.45, 7.05, 'monitor_server', fp=KRB, size=13)
t(ax, 15.45, 6.65, 'Flask :5000  대시보드', fp=KR, size=9, color='#BB99EE')

box(ax, 13.5, 4.7, 3.9, 1.2, '#6B2010', ec='#CC6644', r=0.3, zorder=3)
t(ax, 15.45, 5.45, 'Web / Kiosk', fp=KRB, size=13)
t(ax, 15.45, 5.05, 'alfred_interaction', fp=KR, size=9, color='#DDAA88')

box(ax, 13.5, 3.1, 3.9, 1.2, '#222233', ec='#445566', r=0.3, zorder=3)
t(ax, 15.45, 3.85, 'rosbridge_websocket', fp=KRB, size=12)
t(ax, 15.45, 3.45, ':9090  ROS ↔ Web', fp=KR, size=9, color='#8899AA')

# ── RobotState.msg 작은 박스 ──────────────────────────────────────────────────
box(ax, 0.5, 1.2, 4.2, 2.2, '#11192A', ec='#2A4060', r=0.3, zorder=3)
t(ax, 2.6, 3.2, 'RobotState.msg', fp=KRB, size=10, color='#88BBDD')
t(ax, 2.6, 2.85,'alfred_interfaces', fp=MONO, size=8.5, color='#5577AA')
fields = ['robot_id  /  state  /  pose',
          'battery  /  task_id',
          'task_status  /  timestamp']
for i, f in enumerate(fields):
    t(ax, 2.6, 2.5 - i*0.38, f, fp=MONO, size=8, color='#7799BB')

# ── 화살표 ────────────────────────────────────────────────────────────────────
ROS  = '#E09020'   # ROS 토픽
DATA = '#40C070'   # RobotState
WS   = '#20B0D0'   # WebSocket

# patrol/web → escort_state_bridge
arr(ax, 4.7, 6.9, 5.8, 6.9, ROS)
arr(ax, 4.7, 5.3, 5.8, 6.5, ROS, rad=0.15)
t(ax, 5.25, 7.08, 'nav_status', fp=MONO, size=8, color=ROS, bg=BG)

# escort_state_bridge → state_ws_bridge  (/escort_state)
arr(ax, 9.1, 6.3, 9.1, 4.3, DATA)
t(ax, 9.85, 5.35, '/escort_state', fp=MONO, size=8, color=DATA, bg=BG)

# robot_state_publisher → monitor_server  (/robot_state)
arr(ax, 12.4, 5.3, 13.5, 6.8, DATA, lw=2.5)
t(ax, 13.2, 6.1, '/{robot}/robot_state', fp=MONO, size=8, color=DATA, bg=BG)

# state_ws_bridge → Web/Kiosk  (WebSocket)
arr(ax, 12.4, 3.7, 13.5, 5.1, WS, lw=2.5)
t(ax, 13.2, 4.5, 'WebSocket', fp=MONO, size=8, color=WS, bg=BG)

# nav_status → state_ws_bridge (직접)
arr(ax, 4.7, 6.3, 5.8, 3.7, WS, lw=1.5, rad=0.3)
t(ax, 3.8, 4.2, 'nav_status\n→ ws:9091', fp=MONO, size=7.5, color=WS, bg=BG)

# rosbridge ← ROS topics
ax.annotate('', xy=(13.5, 3.7), xytext=(12.4, 3.7),
            arrowprops=dict(arrowstyle='<-', color='#AAAA44', lw=1.8,
                            shrinkA=6, shrinkB=6), zorder=6)
t(ax, 12.9, 3.9, 'ROS 토픽', fp=KR, size=8, color='#AAAA44', bg=BG)

# robot sensor → robot_state_publisher
ax.annotate('', xy=(5.8, 5.3), xytext=(4.7, 5.3),
            arrowprops=dict(arrowstyle='<-', color='#8888EE', lw=1.8,
                            shrinkA=6, shrinkB=6), zorder=6)
t(ax, 5.25, 5.5, 'amcl_pose\nbattery', fp=MONO, size=7.5, color='#8888EE', bg=BG)

# ── 범례 ──────────────────────────────────────────────────────────────────────
box(ax, 0.3, 0.15, 17.4, 0.75, '#111820', ec='#334455', r=0.2, zorder=4)
items = [
    (ROS,      'ROS2 nav_status 토픽'),
    (DATA,     'RobotState 메시지'),
    (WS,       'WebSocket broadcast'),
    ('#8888EE','센서 데이터'),
    ('#AAAA44','ROS2 토픽 (rosbridge)'),
]
for i, (c, label) in enumerate(items):
    xi = 0.9 + i * 3.4
    yi = 0.52
    ax.plot([xi, xi+0.45], [yi, yi], color=c, lw=2.5, zorder=7)
    ax.annotate('', xy=(xi+0.45, yi), xytext=(xi+0.3, yi),
                arrowprops=dict(arrowstyle='->', color=c, lw=2), zorder=7)
    t(ax, xi+0.6, yi, label, fp=KR, size=8.5, color='#AABBCC', ha='left', bg=BG)

out = '/home/rokey/alfred_ws/docs/alfred_bridge_architecture.png'
plt.savefig(out, dpi=180, bbox_inches='tight', facecolor=BG)
print(f'saved → {out}')
