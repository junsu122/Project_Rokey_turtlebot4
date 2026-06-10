import os
from pathlib import Path

DEFAULT_MODEL = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', 'share',
    'alfred_vision', 'resource', 'best.pt'
)

CONF_THRESH  = 0.7
SNAPSHOT_DIR = Path('/tmp/detection_snapshots')
DEPTH_PATCH  = 4

# 클래스별 confidence 임계값 — YOLO는 CONF_THRESH로 넓게 탐지 후 여기서 후처리
CONF_MAP = {
    'fire':    0.8,
    'patient': 0.8,
    'pistol2': 0.7,
    'knife':   0.7,
    'wallet':  0.7,
    'bag':     0.8,
    'phone':   0.7,
}

# 독 반경 이내에서는 YOLO 추론 스킵 — 충전/도킹 중 오탐 방지
DOCK_RADIUS = 1.0
DOCK_POSITIONS = {
    '/robot2': (-3.2,  2.12),
    '/robot4': (-2.25, 3.0),
}

ROBOT_ID_MAP = {
    '/robot2': 'robot2',
    '/robot4': 'robot4',
}
FLOOR_MAP = {
    '/robot2': 1,
    '/robot4': 2,
}
EVENT_TYPE_MAP = {
    'fire':    'FIRE',
    'patient': 'INJURED_PERSON',
    'pistol2': 'SUSPICIOUS_PERSON',
    'knife':   'SUSPICIOUS_PERSON',
    'wallet':  'LOST_ITEM',
    'bag':     'LOST_ITEM',
    'phone':   'LOST_ITEM',
}
EVENT_COLOR = {
    'FIRE':              (0,   60,  255),
    'INJURED_PERSON':    (0,   165, 255),
    'SUSPICIOUS_PERSON': (0,   255, 255),
    'LOST_ITEM':         (255, 200,   0),
}
