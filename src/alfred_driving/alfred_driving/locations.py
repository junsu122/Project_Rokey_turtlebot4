#!/usr/bin/env python3
"""Shared location data for the multi-robot escort system.

Single source of truth for named locations (floor, owning robot, pose),
the fixed floor-transfer points, and each robot's home/dock location —
imported by escort_node and patrol_node so the map only needs updating
in one place.
"""

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions

# name -> {floor, robot, pose: ([x, y], direction)}
LOCATIONS = {
    # Floor 1 (robot2)
    "entrance":  {"floor": 1, "robot": "robot2", "pose": ([-8.05, 2.56],  TurtleBot4Directions.NORTH)},
    "WC":        {"floor": 1, "robot": "robot2", "pose": ([-7.23, 1.37],  TurtleBot4Directions.NORTH)},
    "info":      {"floor": 1, "robot": "robot2", "pose": ([-5.12, 3.2],   TurtleBot4Directions.NORTH)},
    "entrance2": {"floor": 1, "robot": "robot2", "pose": ([-0.991, 2.48], TurtleBot4Directions.NORTH)},
    "lift":      {"floor": 1, "robot": "robot2", "pose": ([-2.86, 3.82],  TurtleBot4Directions.NORTH)},
    "esc":       {"floor": 1, "robot": "robot2", "pose": ([-5.0, 1.3],    TurtleBot4Directions.NORTH)},
    "station":   {"floor": 1, "robot": "robot2", "pose": ([-2.5, 1.8],   TurtleBot4Directions.EAST)},
    "patrol_1":  {"floor": 1, "robot": "robot2", "pose": ([-7.0, 2.7],   TurtleBot4Directions.EAST)},
    "patrol_2":  {"floor": 1, "robot": "robot2", "pose": ([-7.0, 1.3],   TurtleBot4Directions.NORTH)},
    "patrol_3":  {"floor": 1, "robot": "robot2", "pose": ([-2.7, 2.12],  TurtleBot4Directions.WEST)},
    "patrol_4":  {"floor": 1, "robot": "robot2", "pose": ([-2.7, 3.3],   TurtleBot4Directions.SOUTH)},

    # Floor 2 (robot4)
    "lift2":     {"floor": 2, "robot": "robot4", "pose": ([-1.75, 1.25],  TurtleBot4Directions.NORTH)},
    "esc2":      {"floor": 2, "robot": "robot4", "pose": ([-0.25, 1.25],  TurtleBot4Directions.NORTH)},
    "trans":     {"floor": 2, "robot": "robot4", "pose": ([-0.5, 3.5],    TurtleBot4Directions.NORTH)},
    "gate":      {"floor": 2, "robot": "robot4", "pose": ([-1.8, 2.0],    TurtleBot4Directions.NORTH)},
    "gate_b":    {"floor": 2, "robot": "robot4", "pose": ([-1.3, 2.0],    TurtleBot4Directions.NORTH)},
    "pl_1":      {"floor": 2, "robot": "robot4", "pose": ([-3.0, 3.23],   TurtleBot4Directions.NORTH)},
    "pl_2":      {"floor": 2, "robot": "robot4", "pose": ([-3.0, 2.8],    TurtleBot4Directions.NORTH)},
    "pl_3":      {"floor": 2, "robot": "robot4", "pose": ([-3.0, 2.25],   TurtleBot4Directions.NORTH)},
    "station2":  {"floor": 2, "robot": "robot4", "pose": ([-2.1, 3.2],   TurtleBot4Directions.WEST)},
}

# fixed floor-transfer point: floor 1 'lift' <-> floor 2 'lift2'
TRANSFER = {1: "lift", 2: "lift2"}

# 층간 이동 지점 쌍. scenario_planner/scenario_manager_node에서 출발 위치에 따라 선택
TRANSFER_PAIRS = {
    "lift": {1: "lift", 2: "lift2"},
    "esc":  {1: "esc",  2: "esc2"},
}

# 1층 출발 x 좌표가 이 값보다 작으면 lift/lift2 대신 esc/esc2 사용
ESC_X_THRESHOLD = -5.01

# 각 로봇의 순찰 waypoint 루트 (patrol_node / scenario_manager_node 공용)
PATROL_ROUTES = {
    "robot2": ["patrol_1", "patrol_2", "patrol_3", "patrol_4"],
}

# each robot's home/dock location
HOME = {"robot2": "station", "robot4": "station2"}

# each robot's real starting pose on the map, for AMCL initialization
# (where it physically sits when the launch file starts it)
INITIAL_POSE = {
    "robot2": ([-2.3, 1.5], TurtleBot4Directions.EAST),
    "robot4": ([-2.2, 3.5],  TurtleBot4Directions.WEST),
}
