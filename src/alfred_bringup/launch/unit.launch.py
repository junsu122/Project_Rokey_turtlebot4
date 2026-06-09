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
        # alfred_bridge의 robotX_manager(분산 두뇌)는 ROS2 네임스페이스가 아니라
        # 자체 config의 namespace(예: '/robot2')로 절대경로 토픽을 직접 구성한다
        # (core.py 참고 — tf 리매핑도 노드 내부에서 처리). 여기서 namespace=robot_id를
        # 주면 mock/{robot_id}/cmd 같은 상대경로 토픽이 /robot2/mock/robot2/cmd로
        # 이중 네임스페이스되어 꼬이므로 일부러 제외한다(옛 fms_bridge_node는 진입점이
        # 없어 한 번도 기동된 적 없는 죽은 참조였다 — robotX_manager로 교체).
        Node(package="alfred_bridge", executable=f"{robot_id}_manager",
             name=f"{robot_id}_manager", parameters=[params], output="screen"),
        Node(package="alfred_driving", executable="behavior_node",
             name="behavior_node", **common),
        Node(package="alfred_vision", executable="yolo_monitor_node",
             name="yolo_monitor_node", **common),
        # TODO: Interaction 노드(ui/stt/llm/tts), nav2/localization, video_sender 추가
        #
        # all_robot_manager(전체 모니터)는 robot_id별 유닛이 아니라 두 로봇을 동시에
        # 관찰하는 단일 전역 노드라 여기 포함하지 않는다 — 별도로 한 번만 기동한다:
        #   ros2 run alfred_bridge all_robot_manager
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument("robot_id", default_value="robot2",
                              description="robot2(1층) | robot4(2층)"),
        OpaqueFunction(function=_setup),
    ])
