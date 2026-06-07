#!/usr/bin/env python3
"""FmsLink — FMS와의 MQTT 연결 (paho-mqtt 의존을 이 파일에만 격리).

이 패키지는 별도의 브리지 노드 없이 '로봇 + 브리지'를 겸한다 — 즉
ROS2 쪽(navigator/core)과는 무관하게, 여기서 IF-02(status)/task_ack를
직접 발행하고 IF-03(task)을 직접 구독해 FMS의 fms_server/transport.py와
동일한 프로토콜로 대화한다.

콜백은 paho의 네트워크 스레드에서 호출된다 — core.RobotStateManager가
락으로 동기화한다(이 클래스는 스레드 안전성을 신경 쓰지 않고 그대로 전달만 한다).
"""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Callable

import paho.mqtt.client as mqtt

from . import contract


logger = logging.getLogger('robot_sm.mqtt')

OnTask = Callable[[dict], None]
OnTestCmd = Callable[[dict], None]

# QoS 1 재전송에 대비해 최근 처리한 task_id를 기억해 둔다(브리지 멱등 규칙).
_SEEN_TASK_IDS_MAX = 128


def _test_cmd_topic(robot_id: str) -> str:
    """테스트 전용 제어 채널(계약 외, fms_server/tools/mock_robot.py와 동일) —
    고객 호출(PATROL→INTERACTING) 등 FMS가 모르는 로봇 자체 전이를 재현한다."""
    return f'mock/{robot_id}/cmd'


class FmsLink:
    """FMS 브로커 연결 + IF-02/IF-03/task_ack pub-sub + UI pose 발행."""

    def __init__(self, robot_id: str, host: str, port: int, on_task: OnTask,
                 client_id: str | None = None, keepalive: int = 60,
                 on_test_cmd: OnTestCmd | None = None) -> None:
        self.robot_id = robot_id
        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._on_task = on_task
        self._on_test_cmd = on_test_cmd

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id or f'robot_sm_{robot_id}',
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.message_callback_add(contract.topic_task(robot_id), self._on_task_msg)
        if on_test_cmd is not None:
            self._client.message_callback_add(_test_cmd_topic(robot_id), self._on_test_cmd_msg)

        # 멱등 처리: 이미 본 task_id 재수신 시 무시 (bridge_config 템플릿의 필수 규칙)
        self._seen_task_ids: deque[str] = deque(maxlen=_SEEN_TASK_IDS_MAX)
        self._seen_lock = threading.Lock()

    # ── 연결 수명주기 ─────────────────────────────────────────────────
    def connect(self) -> None:
        logger.info('[%s] MQTT connecting %s:%s', self.robot_id, self._host, self._port)
        self._client.connect(self._host, self._port, self._keepalive)
        self._client.loop_start()   # 백그라운드 네트워크 스레드 (블로킹 아님)

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, _client, _userdata, _flags, reason_code, _props=None) -> None:
        if reason_code != 0:
            logger.error('[%s] MQTT connect failed: %s', self.robot_id, reason_code)
            return
        topic = contract.topic_task(self.robot_id)
        self._client.subscribe(topic, contract.QOS_TASK)
        logger.info('[%s] MQTT connected — subscribed %s (qos=%s)',
                    self.robot_id, topic, contract.QOS_TASK)
        if self._on_test_cmd is not None:
            test_topic = _test_cmd_topic(self.robot_id)
            self._client.subscribe(test_topic, qos=1)
            logger.info('[%s] MQTT — subscribed %s (테스트 전용, 계약 외)',
                        self.robot_id, test_topic)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _props=None) -> None:
        if reason_code == 0:
            logger.info('[%s] MQTT disconnected (normal)', self.robot_id)
        else:
            logger.warning('[%s] MQTT disconnected unexpectedly: %s', self.robot_id, reason_code)

    # ── IF-03 수신 (task) — 멱등 필터링 후 core로 전달 ──────────────────
    def _on_task_msg(self, _client, _userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as err:
            logger.error('[%s] non-JSON task message: %s', self.robot_id, err)
            return

        task_id = payload.get('task_id')
        with self._seen_lock:
            if task_id is not None and task_id in self._seen_task_ids:
                logger.info('[%s] 중복 task_id=%s 재수신 — 무시(QoS1 재전송)', self.robot_id, task_id)
                return
            self._seen_task_ids.append(task_id)

        try:
            self._on_task(payload)
        except Exception:
            logger.exception('[%s] task 핸들러 오류', self.robot_id)

    # ── 테스트 전용 제어 채널(계약 외) — 고객 호출 등 로봇 자체 전이 재현 ──
    def _on_test_cmd_msg(self, _client, _userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as err:
            logger.error('[%s] non-JSON test cmd message: %s', self.robot_id, err)
            return
        try:
            self._on_test_cmd(payload)
        except Exception:
            logger.exception('[%s] test cmd 핸들러 오류', self.robot_id)

    # ── 발행: IF-02 status / task_ack / UI pose ────────────────────────
    def publish_status(self, payload: dict) -> None:
        self._publish(contract.topic_status(self.robot_id), payload, contract.QOS_STATUS)

    def publish_task_ack(self, payload: dict) -> None:
        self._publish(contract.topic_task_ack(self.robot_id), payload, contract.QOS_TASK_ACK)

    def publish_ui_pose(self, topic: str, payload: dict, qos: int = 0) -> None:
        """FMS 계약과 무관한 별도 채널 — 같은 broker에 좌표만 알린다(UI 트랙과 합의 필요)."""
        self._publish(topic, payload, qos)

    def _publish(self, topic: str, payload: dict, qos: int) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        info = self._client.publish(topic, data, qos=qos)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning('[%s] publish 실패 rc=%s topic=%s', self.robot_id, info.rc, topic)
