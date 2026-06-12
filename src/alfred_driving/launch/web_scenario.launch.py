#!/usr/bin/env python3
"""웹에서 전달되는 일반/시각장애인 안내 시나리오를 실행한다."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    alfred_share = get_package_share_directory('alfred_driving')

    camera_index = LaunchConfiguration('camera_index')
    marker_size_m = LaunchConfiguration('marker_size_m')
    marker_ids = LaunchConfiguration('marker_ids')
    use_aruco = LaunchConfiguration('use_aruco')
    aruco_start_delay = LaunchConfiguration('aruco_start_delay')
    patrol_robot = LaunchConfiguration('patrol_robot')
    start_rosbridge = LaunchConfiguration('start_rosbridge')
    start_request_bridge = LaunchConfiguration('start_request_bridge')
    start_scenario_manager = LaunchConfiguration('start_scenario_manager')
    start_patrol = LaunchConfiguration('start_patrol')

    return LaunchDescription([
        DeclareLaunchArgument('camera_index', default_value='0'),
        DeclareLaunchArgument('marker_size_m', default_value='0.165'),
        DeclareLaunchArgument('marker_ids', default_value='[0, 1]'),
        DeclareLaunchArgument('use_aruco', default_value='false'),
        DeclareLaunchArgument(
            'start_rosbridge',
            default_value='true',
            description='Start the custom websocket rosbridge_node on port 9090.',
        ),
        DeclareLaunchArgument(
            'start_request_bridge',
            default_value='true',
            description='Start server_request_node to convert /information into /scenario_request.',
        ),
        DeclareLaunchArgument(
            'start_scenario_manager',
            default_value='true',
            description='Start scenario_manager_node.',
        ),
        DeclareLaunchArgument(
            'start_patrol',
            default_value='true',
            description='Start robot2 patrol_node from this launch.',
        ),
        DeclareLaunchArgument(
            'aruco_start_delay',
            default_value='10.0',
            description='Seconds to wait before starting ArUco nodes when use_aruco is true.',
        ),
        DeclareLaunchArgument('patrol_robot', default_value='robot2'),
        DeclareLaunchArgument(
            'start_nav2',
            default_value='false',
            description=(
                'Deprecated no-op. Nav2/localization must be started separately '
                '(for example l2, rv2, n2, l4, rv4, n4).'
            ),
        ),
        DeclareLaunchArgument(
            'robot2_map',
            default_value=os.path.join(alfred_share, 'resource', 'map', 'map_1.yaml'),
            description='Deprecated no-op. robot2 localization is started outside this launch.',
        ),
        DeclareLaunchArgument(
            'robot4_map',
            default_value=os.path.join(alfred_share, 'resource', 'map', 'map_2_1.yaml'),
            description='Deprecated no-op. robot4 localization is started outside this launch.',
        ),

        Node(
            package='alfred_driving',
            executable='rosbridge_node',
            output='screen',
            condition=IfCondition(start_rosbridge),
        ),
        Node(
            package='alfred_driving',
            executable='server_request_node',
            output='screen',
            condition=IfCondition(start_request_bridge),
        ),
        Node(
            package='alfred_driving',
            executable='scenario_manager_node',
            output='screen',
            parameters=[{'patrol_robot': patrol_robot}],
            condition=IfCondition(start_scenario_manager),
        ),
        # Node(
        #     package='alfred_driving',
        #     executable='navigation_node',
        #     output='screen',
        #     parameters=[{'robot_namespace': 'robot4'}],
        # ),
        Node(
            package='alfred_driving',
            executable='patrol_node',
            output='screen',
            condition=IfCondition(start_patrol),
        ),
        TimerAction(
            period=aruco_start_delay,
            condition=IfCondition(use_aruco),
            actions=[
                Node(
                    package='alfred_driving',
                    executable='aruco_tracker_node',
                    output='screen',
                    parameters=[{
                        'camera_index': camera_index,
                        'marker_size_m': marker_size_m,
                        'marker_ids': marker_ids,
                    }],
                ),
                Node(
                    package='alfred_driving',
                    executable='marker_speed_governor',
                    name='robot2_marker_speed_governor',
                    output='screen',
                    parameters=[{
                        'namespace': 'robot2',
                        'enabled': False,
                        'enable_topic': '/robot2/escort_marker_mode',
                    }],
                ),
                Node(
                    package='alfred_driving',
                    executable='marker_speed_governor',
                    name='robot4_marker_speed_governor',
                    output='screen',
                    parameters=[{
                        'namespace': 'robot4',
                        'enabled': False,
                        'enable_topic': '/robot4/escort_marker_mode',
                    }],
                ),
            ],
        ),
    ])
