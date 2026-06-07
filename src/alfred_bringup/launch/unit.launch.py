#!/usr/bin/env python3
"""로봇 유닛 1대 통합 기동.

사용:
  ros2 launch alfred_bringup unit.launch.py robot_id:=robot2
  ros2 launch alfred_bringup unit.launch.py robot_id:=robot4

robot_id에 맞는 config/<robot_id>.yaml 파라미터를 모든 노드에 주입하고,
해당 네임스페이스 아래에 브리지/주행/비전 노드를 띄운다.
Interaction(STT/LLM/TTS/UI)·nav2 스택은 필요 시 주석 해제/별도 launch로 확장.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    robot_id = LaunchConfiguration("robot_id").perform(context)
    share = get_package_share_directory("alfred_bringup")
    params = os.path.join(share, "config", f"{robot_id}.yaml")

    common = dict(namespace=robot_id, parameters=[params], output="screen")

    return [
        Node(package="alfred_bridge", executable="fms_bridge_node",
             name="fms_bridge_node", **common),
        Node(package="alfred_driving", executable="behavior_node",
             name="behavior_node", **common),
        Node(package="alfred_vision", executable="yolo_monitor_node",
             name="yolo_monitor_node", **common),
        # TODO: Interaction 노드(ui/stt/llm/tts), nav2/localization, video_sender 추가
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument("robot_id", default_value="robot2",
                              description="robot2(1층) | robot4(2층)"),
        OpaqueFunction(function=_setup),
    ])
