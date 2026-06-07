"""맵 빌드 — docs/maps/*.pgm+yaml → web/maps/*.png + maps.json.

ROS occupancy grid(pgm)는 브라우저가 못 읽으니 png로 변환하고, 좌표 변환에 필요한
메타(resolution, origin, 픽셀 크기)를 maps.json에 모은다. 맵 갱신(re-SLAM) 시 재실행.

실행: python3 tools/build_maps.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]          # test_alfred
SRC = ROOT / "docs" / "maps"
OUT = Path(__file__).resolve().parents[1] / "web" / "maps"

# 로봇 ↔ 층 매핑 (robot2=1층, robot4=2층). config와 일치.
FLOORS = [
    {"floor": 1, "robot_id": "robot2", "src": "map_1"},
    {"floor": 2, "robot_id": "robot4", "src": "map_2"},
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    floors = []
    for f in FLOORS:
        meta = yaml.safe_load((SRC / f"{f['src']}.yaml").read_text())
        img = Image.open(SRC / f"{f['src']}.pgm").convert("L")
        img.save(OUT / f"{f['src']}.png")
        floors.append({
            "floor": f["floor"],
            "robot_id": f["robot_id"],
            "image": f"maps/{f['src']}.png",
            "resolution": meta["resolution"],
            "origin": meta["origin"][:2],     # [x, y] (theta 무시)
            "width": img.size[0],
            "height": img.size[1],
        })
        print(f"  {f['src']}.png  {img.size}px  res={meta['resolution']}  origin={meta['origin'][:2]}")

    (OUT / "maps.json").write_text(json.dumps({"floors": floors}, ensure_ascii=False, indent=2))
    print(f"built {len(floors)} floors → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
