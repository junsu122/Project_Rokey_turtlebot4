#!/usr/bin/env python3
"""웹 기반 로봇 호출을 위한 시나리오 파싱 및 경로 계획 로직."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from alfred_driving.locations import LOCATIONS, TRANSFER_PAIRS


@dataclass(frozen=True)
class PersonRequest:
    request_id: str
    person_type: str
    mode: str
    origin_name: Optional[str]
    origin_floor: int
    origin_x: float
    destination_name: str

    @property
    def blind_mode(self) -> bool:
        blind_values = {'blind', 'visually_impaired', 'visual_impaired'}
        return self.mode in blind_values or self.person_type in blind_values


@dataclass(frozen=True)
class RoutePlan:
    request: PersonRequest
    destination_robot: str
    same_floor: bool
    transfer_kind: Optional[str]
    transfer_origin_name: Optional[str]
    transfer_destination_name: Optional[str]
    destination_waypoint_names: Tuple[str, ...]


def unwrap_rosbridge_payload(data: dict[str, Any]) -> dict[str, Any]:
    """일반 웹 JSON과 rosbridge publish envelope 형식을 모두 허용한다."""
    return data.get('msg', data)


def parse_person_request(payload: dict[str, Any]) -> PersonRequest:
    destination = _destination_name(payload)
    if destination not in LOCATIONS:
        raise ValueError(f"unknown destination '{destination}'")

    origin_name = _optional_string(payload, 'origin', 'poi_id')
    if origin_name and origin_name in LOCATIONS:
        origin_floor = int(LOCATIONS[origin_name]['floor'])
        origin_x = float(LOCATIONS[origin_name]['pose'][0][0])
    else:
        origin = payload.get('origin') or payload.get('location') or {}
        if not isinstance(origin, dict):
            origin = {}
        origin_pose = origin.get('pose') if isinstance(origin, dict) else {}
        origin_floor = int(origin.get('floor', payload.get('origin_floor', 1)))
        origin_x = float(
            origin.get(
                'x',
                origin_pose.get('x', payload.get('origin_x', 0.0))
                if isinstance(origin_pose, dict)
                else payload.get('origin_x', 0.0),
            )
        )

    customer = payload.get('customer') if isinstance(payload.get('customer'), dict) else {}
    raw_person_type = (
        payload.get('person_type')
        or payload.get('user_type')
        or payload.get('type')
        or customer.get('profile')
        or 'normal'
    )
    raw_mode = payload.get('mode') or customer.get('profile') or raw_person_type
    person_type = normalize_person_type(raw_person_type)
    mode = normalize_person_type(raw_mode)

    return PersonRequest(
        request_id=str(payload.get('request_id', '')),
        person_type=person_type,
        mode=mode,
        origin_name=origin_name,
        origin_floor=origin_floor,
        origin_x=origin_x,
        destination_name=destination,
    )


def build_route_plan(request: PersonRequest) -> RoutePlan:
    destination = LOCATIONS[request.destination_name]
    destination_floor = int(destination['floor'])
    same_floor = request.origin_floor == destination_floor
    destination_waypoints = destination_route_names(request)

    if same_floor:
        return RoutePlan(
            request=request,
            destination_robot=str(destination['robot']),
            same_floor=True,
            transfer_kind=None,
            transfer_origin_name=None,
            transfer_destination_name=None,
            destination_waypoint_names=destination_waypoints,
        )

    transfer_kind = select_transfer_kind(request)
    pair = TRANSFER_PAIRS[transfer_kind]
    return RoutePlan(
        request=request,
        destination_robot=str(destination['robot']),
        same_floor=False,
        transfer_kind=transfer_kind,
        transfer_origin_name=pair[request.origin_floor],
        transfer_destination_name=pair[destination_floor],
        destination_waypoint_names=destination_waypoints,
    )


def select_transfer_kind(request: PersonRequest) -> str:
    return 'lift' if request.blind_mode else 'esc'


def normalize_person_type(value: Any) -> str:
    blind_values = {'blind', 'visually_impaired', 'visual_impaired'}
    return 'blind' if str(value).strip().lower() in blind_values else 'normal'


def destination_route_names(request: PersonRequest) -> Tuple[str, ...]:
    """목적지까지 이동할 waypoint 순서를 반환한다.

    2층에서는 일반 사용자는 gate를, 시각장애인은 gate_b를 먼저 거친 뒤
    최종 목적지로 이동한다.
    """
    destination = LOCATIONS[request.destination_name]
    if int(destination['floor']) != 2:
        return (request.destination_name,)

    gate_name = 'gate_b' if request.blind_mode else 'gate'
    if request.destination_name == gate_name:
        return (request.destination_name,)
    return (gate_name, request.destination_name)


def _destination_name(payload: dict[str, Any]) -> str:
    destination = payload.get('destination') or {}
    value = (
        destination.get('poi_id')
        or destination.get('name')
        or payload.get('destination_name')
        or payload.get('poi_id')
        or payload.get('goal')
    )
    if not value:
        raise ValueError('destination is missing')
    return str(value)


def _optional_string(payload: dict[str, Any], key: str, subkey: str) -> Optional[str]:
    value = payload.get(key)
    if isinstance(value, dict):
        item = value.get(subkey) or value.get('name')
        return str(item) if item else None
    return str(value) if value else None
