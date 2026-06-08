"""MQTT transport wrapper.

설계 의도(구현가이드 §3):
  전송 프로토콜이 공식 미확정(MQTT 권장안)이므로 publish/subscribe 인터페이스를
  클래스로 감싸 다른 프로토콜(WebSocket 등)로 교체 가능성을 남긴다.
  다른 모듈은 paho를 직접 import하지 않는다 — 전부 이 Transport를 통한다.

The monitoring server subscribes to status/event topics only. ``publish`` is
kept for test/demo tools, not for robot control.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable

import paho.mqtt.client as mqtt

import config


logger = logging.getLogger("monitor.transport")

# 수신 핸들러 시그니처: (topic: str, payload: dict) -> None
MessageHandler = Callable[[str, dict], None]


class MqttTransport:
    """JSON pub/sub 래퍼. 구독은 (topic_filter, qos, handler)로 등록한다."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: str | None = None,
        keepalive: int | None = None,
    ) -> None:
        self.host = host or config.MQTT_HOST
        self.port = port or config.MQTT_PORT
        self.keepalive = keepalive or config.MQTT_KEEPALIVE
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id or config.MQTT_CLIENT_ID,
        )
        # 재접속 시 자동 재구독을 위해 구독 목록 보관: {topic_filter: (qos, handler)}
        self._subscriptions: dict[str, tuple[int, MessageHandler]] = {}
        # _subscriptions 변경(subscribe)과 _on_connect 순회 간 race 방지.
        self._sub_lock = threading.Lock()
        self._connected = False
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    # ── 연결 수명주기 ────────────────────────────────────────────────────
    def connect(self) -> None:
        logger.info("MQTT connecting to %s:%s", self.host, self.port)
        self._client.connect(self.host, self.port, self.keepalive)

    def loop_start(self) -> None:
        """백그라운드 네트워크 루프 시작 (블로킹 아님 — 절대 규칙 2)."""
        self._client.loop_start()

    def loop_stop(self) -> None:
        self._client.loop_stop()

    def disconnect(self) -> None:
        self._client.disconnect()

    # ── Publish helper for tests/demo messages. ─────────────────────────
    def publish(self, topic: str, payload: dict, qos: int = 1) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        info = self._client.publish(topic, data, qos=qos)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("publish failed rc=%s topic=%s", info.rc, topic)
        else:
            logger.debug("published topic=%s payload=%s", topic, data)

    # ── Subscribe to JSON MQTT topics. ──────────────────────────────────
    def subscribe(self, topic_filter: str, handler: MessageHandler, qos: int = 0) -> None:
        """topic_filter(와일드카드 가능)에 핸들러 등록. 연결 전후 모두 호출 가능."""
        self._client.message_callback_add(topic_filter, self._wrap(handler))
        with self._sub_lock:
            self._subscriptions[topic_filter] = (qos, handler)
            do_now = self._connected
        # 이미 연결돼 있으면 즉시 구독, 아니면 _on_connect가 일괄 구독한다.
        if do_now:
            self._client.subscribe(topic_filter, qos)

    def _wrap(self, handler: MessageHandler):
        def _cb(_client, _userdata, msg) -> None:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as err:
                logger.error("non-JSON message on %s: %s", msg.topic, err)
                return
            try:
                handler(msg.topic, payload)
            except Exception:  # 핸들러 예외가 네트워크 루프를 죽이지 않도록 격리
                logger.exception("handler error on %s", msg.topic)

        return _cb

    # ── paho 콜백 ────────────────────────────────────────────────────────
    def _on_connect(self, _client, _userdata, _flags, reason_code, _properties=None) -> None:
        if reason_code != 0:
            logger.error("MQTT connect failed: %s", reason_code)
            return
        logger.info("MQTT connected")
        # 재접속 포함 — 등록된 모든 구독을 다시 적용 (스냅샷으로 순회 중 변경 방지)
        with self._sub_lock:
            self._connected = True
            items = list(self._subscriptions.items())
        for topic_filter, (qos, _handler) in items:
            self._client.subscribe(topic_filter, qos)
            logger.info("subscribed %s (qos=%s)", topic_filter, qos)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties=None) -> None:
        with self._sub_lock:
            self._connected = False
        # 정상 종료(rc=0)는 INFO, 예기치 않은 끊김만 WARNING
        if reason_code == 0:
            logger.info("MQTT disconnected (normal)")
        else:
            logger.warning("MQTT disconnected unexpectedly: %s", reason_code)
