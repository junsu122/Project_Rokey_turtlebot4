#!/usr/bin/env python3
"""기존 ArUco/순찰 통합 노드에 대한 호환 안내.

현재는 순찰과 ArUco 기능을 의도적으로 분리했다.

- patrol_node는 robot2 대기 순찰과 시나리오 목표를 제어한다.
- aruco_tracker_node는 마커를 검출한다.
- marker_speed_governor는 안내 구간의 ArUco 기반 속도 제한을 적용한다.
"""


def main(args=None):
    del args
    print(
        'aruco_marker_patrol_robot4 is no longer used. '
        'Run patrol_node for patrol, and aruco_tracker_node + '
        'marker_speed_governor for ArUco speed control.'
    )


if __name__ == '__main__':
    main()
