import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    params = os.path.join(
        get_package_share_directory('alfred_vision'),
        'config', 'params.yaml',
    )

    return LaunchDescription([
        Node(
            package='alfred_vision',
            executable='detector',
            name='detector_robot2',
            parameters=[params],
            remappings=[
                ('/tf',        '/robot2/tf'),
                ('/tf_static', '/robot2/tf_static'),
            ],
            output='screen',
        ),
        Node(
            package='alfred_vision',
            executable='detector',
            name='detector_robot4',
            parameters=[params],
            remappings=[
                ('/tf',        '/robot4/tf'),
                ('/tf_static', '/robot4/tf_static'),
            ],
            output='screen',
        ),
        Node(
            package='alfred_vision',
            executable='event_handler',
            name='event_handler_robot2',
            parameters=[params],
            output='screen',
        ),
        Node(
            package='alfred_vision',
            executable='event_handler',
            name='event_handler_robot4',
            parameters=[params],
            output='screen',
        ),
    ])
