#!/usr/bin/env python3
"""웹에서 전달되는 일반/시각장애인 안내 시나리오를 실행한다."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def turtlebot4_launch_file(name: str) -> str:
    """turtlebot4_navigation 패키지의 launch 파일 경로를 만든다."""
    return os.path.join(
        get_package_share_directory('turtlebot4_navigation'),
        'launch',
        name,
    )


def generate_launch_description():
    alfred_share = get_package_share_directory('alfred_driving')

    camera_index = LaunchConfiguration('camera_index')
    marker_size_m = LaunchConfiguration('marker_size_m')
    marker_ids = LaunchConfiguration('marker_ids')
    use_aruco = LaunchConfiguration('use_aruco')
    patrol_robot = LaunchConfiguration('patrol_robot')
    start_nav2 = LaunchConfiguration('start_nav2')
    robot2_map = LaunchConfiguration('robot2_map')
    robot4_map = LaunchConfiguration('robot4_map')

    return LaunchDescription([
        DeclareLaunchArgument('camera_index', default_value='0'),
        DeclareLaunchArgument('marker_size_m', default_value='0.165'),
        DeclareLaunchArgument('marker_ids', default_value='[0, 1]'),
        DeclareLaunchArgument('use_aruco', default_value='false'),
        DeclareLaunchArgument('patrol_robot', default_value='robot2'),
        DeclareLaunchArgument(
            'start_nav2',
            default_value='false',
            description='true이면 robot2/robot4 localization과 Nav2를 함께 실행한다.',
        ),
        DeclareLaunchArgument(
            'robot2_map',
            default_value=os.path.join(alfred_share, 'resource', 'map', 'map_1.yaml'),
            description='robot2 localization map yaml',
        ),
        DeclareLaunchArgument(
            'robot4_map',
            default_value=os.path.join(alfred_share, 'resource', 'map', 'map_2_1.yaml'),
            description='robot4 localization map yaml',
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot4_launch_file('localization.launch.py')),
            condition=IfCondition(start_nav2),
            launch_arguments={
                'namespace': '/robot2',
                'map': robot2_map,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot4_launch_file('nav2.launch.py')),
            condition=IfCondition(start_nav2),
            launch_arguments={
                'namespace': '/robot2',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot4_launch_file('localization.launch.py')),
            condition=IfCondition(start_nav2),
            launch_arguments={
                'namespace': '/robot4',
                'map': robot4_map,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot4_launch_file('nav2.launch.py')),
            condition=IfCondition(start_nav2),
            launch_arguments={
                'namespace': '/robot4',
            }.items(),
        ),

        Node(
            package='alfred_driving',
            executable='rosbridge_node',
            output='screen',
        ),
        Node(
            package='alfred_driving',
            executable='server_request_node',
            output='screen',
        ),
        Node(
            package='alfred_driving',
            executable='scenario_manager_node',
            output='screen',
            parameters=[{'patrol_robot': patrol_robot}],
        ),
        Node(
            package='alfred_driving',
            executable='navigation_node',
            output='screen',
            parameters=[{'robot_namespace': 'robot4'}],
        ),
        Node(
            package='alfred_driving',
            executable='patrol_node',
            output='screen',
        ),
        Node(
            package='alfred_driving',
            executable='aruco_tracker_node',
            output='screen',
            condition=IfCondition(use_aruco),
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
            condition=IfCondition(use_aruco),
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
            condition=IfCondition(use_aruco),
            parameters=[{
                'namespace': 'robot4',
                'enabled': False,
                'enable_topic': '/robot4/escort_marker_mode',
            }],
        ),
    ])
