"""POI 테이블 조회 헬퍼 — poi_id → goal(좌표/층) 변환.

좌표는 poi_table.yaml에서 온다(값은 맵 작성 후 확정, 현재 스텁).
IF-03 goal 형식: {poi_id, floor, pose:{x,y,theta}}.
"""

from __future__ import annotations

from . import config


_table: dict[str, dict] | None = None


def table() -> dict[str, dict]:
    global _table
    if _table is None:
        _table = config.load_poi_table()
    return _table


def reload() -> None:
    """테스트/맵 갱신용 — 캐시 무효화."""
    global _table
    _table = None


def get(poi_id: str) -> dict | None:
    return table().get(poi_id)


def by_type(poi_type: str) -> dict[str, dict]:
    return {pid: p for pid, p in table().items() if p.get("type") == poi_type}


def first_of_type(poi_type: str) -> str | None:
    items = by_type(poi_type)
    return next(iter(items), None)


def goal_for(poi_id: str | None) -> dict | None:
    """poi_id → IF-03 goal dict. 없으면 None."""
    if not poi_id:
        return None
    p = get(poi_id)
    if not p:
        return None
    return {"poi_id": poi_id, "floor": p.get("floor"), "pose": p.get("pose", {})}
