#!/usr/bin/env python3
"""웹 기반 robot2/robot4 시나리오에서 공유하는 위치 데이터.

이 파일은 이름이 붙은 위치(층, 담당 로봇, pose), 층간 이동 지점,
각 로봇의 복귀/도킹 위치를 관리하는 단일 기준이다.
"""

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions

# 이름 -> {floor, robot, pose: ([x, y], direction)}
LOCATIONS = {
    # 1층 위치(robot2 담당)
    "entrance":  {"floor": 1, "robot": "robot2", "pose": ([-8.05, 2.56],  TurtleBot4Directions.NORTH)},
    "WC":        {"floor": 1, "robot": "robot2", "pose": ([-7.23, 1.37],  TurtleBot4Directions.NORTH)},
    "info":      {"floor": 1, "robot": "robot2", "pose": ([-5.12, 3.2],   TurtleBot4Directions.NORTH)},
    "entrance2": {"floor": 1, "robot": "robot2", "pose": ([-0.991, 2.48], TurtleBot4Directions.NORTH)},
    "lift":      {"floor": 1, "robot": "robot2", "pose": ([-2.86, 3.82],  TurtleBot4Directions.NORTH)},
    "esc":       {"floor": 1, "robot": "robot2", "pose": ([-5.0, 1.5],    TurtleBot4Directions.EAST)},
    "station":   {"floor": 1, "robot": "robot2", "pose": ([-2.5, 1.8],   TurtleBot4Directions.EAST)},
    "patrol_1":  {"floor": 1, "robot": "robot2", "pose": ([-7.0, 2.7],   TurtleBot4Directions.EAST)},
    "patrol_2":  {"floor": 1, "robot": "robot2", "pose": ([-7.0, 1.3],   TurtleBot4Directions.NORTH)},
    "patrol_3":  {"floor": 1, "robot": "robot2", "pose": ([-2.7, 2.12],  TurtleBot4Directions.WEST)},
    "patrol_4":  {"floor": 1, "robot": "robot2", "pose": ([-2.7, 3.3],   TurtleBot4Directions.SOUTH)},

    # 2층 위치(robot4 담당)
    "lift2":     {"floor": 2, "robot": "robot4", "pose": ([-1.75, 1.25],  TurtleBot4Directions.NORTH)},
    "esc2":      {"floor": 2, "robot": "robot4", "pose": ([-0.25, 1.25],  TurtleBot4Directions.NORTH)},
    "trans":     {"floor": 2, "robot": "robot4", "pose": ([-0.5, 3.5],    TurtleBot4Directions.NORTH)},
    "gate":      {"floor": 2, "robot": "robot4", "pose": ([-2.1, 2.0],    TurtleBot4Directions.WEST)},
    "gate_b":    {"floor": 2, "robot": "robot4", "pose": ([-1.3, 2.0],    TurtleBot4Directions.WEST)},
    "pl_1":      {"floor": 2, "robot": "robot4", "pose": ([-3.0, 3.23],   TurtleBot4Directions.NORTH)},
    "pl_2":      {"floor": 2, "robot": "robot4", "pose": ([-3.0, 2.8],    TurtleBot4Directions.NORTH)},
    "pl_3":      {"floor": 2, "robot": "robot4", "pose": ([-3.0, 2.25],   TurtleBot4Directions.NORTH)},
    "station2":  {"floor": 2, "robot": "robot4", "pose": ([-2.1, 3.2],   TurtleBot4Directions.WEST)},
}

# 층간 이동 지점 쌍. 1층 출발 위치에 따라 사용할 쌍을 선택한다.
TRANSFER_PAIRS = {
    "lift": {1: "lift", 2: "lift2"},
    "esc": {1: "esc", 2: "esc2"},
}

# 기본 층간 이동 지점: 1층 'lift' <-> 2층 'lift2'.
TRANSFER = TRANSFER_PAIRS["lift"]

# 1층 출발 x 좌표가 이 값보다 작으면 lift/lift2 대신 esc/esc2를 사용한다.
ESC_X_THRESHOLD = -5.01

# 각 로봇의 복귀/도킹 위치
HOME = {"robot2": "station", "robot4": "station2"}

# 로봇별 순찰 waypoint 루프. 각 이름은 LOCATIONS에 반드시 존재해야 한다.
PATROL_ROUTES = {
    "robot2": ["patrol_1", "patrol_2", "patrol_3", "patrol_4"],
    # "robot4": ["pl_3", "gate"],
}

# AMCL 초기화를 위한 각 로봇의 실제 시작 pose
# launch 실행 시 로봇이 물리적으로 놓여 있는 위치를 기준으로 한다.
INITIAL_POSE = {
    "robot2": ([-2.3, 1.5], TurtleBot4Directions.EAST),
    "robot4": ([-2.2, 3.5],  TurtleBot4Directions.WEST),
}
