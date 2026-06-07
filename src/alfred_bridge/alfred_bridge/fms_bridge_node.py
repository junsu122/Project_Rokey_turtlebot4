#!/usr/bin/env python3
"""fms_bridge_node — ROS ↔ MQTT/IF 양방향 번역 (유닛당 1개).

설계 기준: docs/INTERFACE_CONTRACT.md (IF-01~05, 토픽, QoS — 계약 고정).
  ros2mqtt : 유닛 내부 ROS 토픽 구독 → IF JSON 포장 → robot/{id}/... 발행
  mqtt2ros : robot/{id}/task(IF-03) 구독 → ROS 토픽 재발행 → Driving 수행

⚠️ 이 노드는 FMS와의 유일한 통신 창구다. paho-mqtt 의존을 이 패키지에만 둔다.

TODO(통합팀):
  - 각 mapping의 ros_topic/ros_type를 실제 트랙 토픽으로 연결 (bridge_config.template.yaml)
  - msg ↔ IF JSON 변환 함수 채우기 (to_if02 / from_if03 등)
  - 멱등: 처리한 task_id 재수신 시 무시 (계약 §1.3)
  - 거절 규칙: PATROL/IDLE 상태 ESCORT task는 REJECT (계약 §6.2)
"""
from __future__ import annotations

import json

import rclpy
from rclpy.node import Node

from alfred_interfaces.msg import Event, Request, RobotState, Task, TaskAck

try:
    import paho.mqtt.client as mqtt
except ImportError as exc:  # pragma: no cover
    raise SystemExit("paho-mqtt 필요: pip install paho-mqtt") from exc


class FmsBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("fms_bridge_node")

        # ── 파라미터 (bringup launch에서 robot2.yaml/robot4.yaml로 주입) ──
        self.declare_parameter("robot_id", "robot2")
        self.declare_parameter("broker_host", "192.168.0.20")
        self.declare_parameter("broker_port", 1883)
        self.declare_parameter("client_id", "bridge_robot2")  # ⚠ 유닛마다 유일

        self.robot_id = self.get_parameter("robot_id").value
        host = self.get_parameter("broker_host").value
        port = self.get_parameter("broker_port").value
        client_id = self.get_parameter("client_id").value

        self._seen_task_ids: set[str] = set()  # 멱등용

        # ── MQTT ──
        self._mqtt = mqtt.Client(client_id=client_id)
        self._mqtt.on_connect = self._on_mqtt_connect
        self._mqtt.on_message = self._on_mqtt_message
        self.get_logger().info(f"MQTT 연결 시도: {host}:{port} (id={client_id})")
        self._mqtt.connect(host, port, keepalive=60)
        self._mqtt.loop_start()

        # ── ROS pubs (mqtt2ros: IF-03 task 재발행) ──
        self.pub_task = self.create_publisher(Task, f"/{self.robot_id}/fms/task", 10)

        # ── ROS subs (ros2mqtt: 보고 IF들) ──
        self.create_subscription(RobotState, f"/{self.robot_id}/robot_state", self._on_robot_state, 10)
        self.create_subscription(Request, f"/{self.robot_id}/ui/request", self._on_request, 10)
        self.create_subscription(Event, f"/{self.robot_id}/vision/alert", self._on_event, 10)
        self.create_subscription(TaskAck, f"/{self.robot_id}/fms/task_ack", self._on_task_ack, 10)

    # ── MQTT 콜백 ──
    def _on_mqtt_connect(self, client, userdata, flags, rc) -> None:
        topic = f"robot/{self.robot_id}/task"
        client.subscribe(topic, qos=1)
        self.get_logger().info(f"MQTT 연결됨(rc={rc}), 구독: {topic}")

    def _on_mqtt_message(self, client, userdata, msg) -> None:
        # mqtt2ros: IF-03 task 수신 → Task.msg 재발행
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.get_logger().error(f"잘못된 JSON: {msg.topic}")
            return
        task_id = payload.get("task_id")
        if task_id in self._seen_task_ids:  # 멱등
            return
        self._seen_task_ids.add(task_id)
        # TODO: payload(IF-03) → Task.msg 변환 후 self.pub_task.publish(...)
        self.get_logger().info(f"IF-03 task 수신: {task_id} (변환 TODO)")

    # ── ROS 콜백 (ros2mqtt) ──
    def _on_robot_state(self, msg: RobotState) -> None:
        # TODO: RobotState → IF-02 JSON → publish robot/{id}/status (qos 0)
        pass

    def _on_request(self, msg: Request) -> None:
        # TODO: Request → IF-01 JSON → publish robot/{id}/request (qos 1)
        pass

    def _on_event(self, msg: Event) -> None:
        # TODO: Event → IF-05 JSON → publish robot/{id}/event (qos 1)
        pass

    def _on_task_ack(self, msg: TaskAck) -> None:
        # TODO: TaskAck → JSON → publish robot/{id}/task_ack (qos 1)
        pass

    def destroy_node(self) -> bool:
        self._mqtt.loop_stop()
        self._mqtt.disconnect()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FmsBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
