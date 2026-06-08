"""MQTT to SQLite bridge for the standalone 3D monitoring UI.

Run this on the PC that owns the SQLite file.  Other PCs/robots on the same
Wi-Fi can publish JSON messages to the MQTT broker, and this bridge records
them into viz_3d/data/monitor.db by default.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import ssl
import threading
from typing import Callable

import monitor_db as db


logger = logging.getLogger("viz_3d.db_bridge")

MQTT_HOST = os.getenv("MONITOR_MQTT_HOST", "localhost")
MQTT_TLS = os.getenv("MONITOR_MQTT_TLS", "0").strip().lower() in ("1", "true", "yes", "on")
MQTT_PORT = int(os.getenv("MONITOR_MQTT_PORT", "8883" if MQTT_TLS else "1883"))
MQTT_KEEPALIVE = int(os.getenv("MONITOR_MQTT_KEEPALIVE", "60"))
MQTT_CLIENT_ID = os.getenv("MONITOR_MQTT_CLIENT_ID", "viz_3d_db_bridge")
MQTT_USER = os.getenv("MONITOR_MQTT_USER")
MQTT_PASSWORD = os.getenv("MONITOR_MQTT_PASSWORD")
MQTT_CA_CERT = os.getenv("MONITOR_MQTT_CA_CERT")
MQTT_CERTFILE = os.getenv("MONITOR_MQTT_CERTFILE")
MQTT_KEYFILE = os.getenv("MONITOR_MQTT_KEYFILE")
MQTT_TLS_INSECURE = os.getenv("MONITOR_MQTT_TLS_INSECURE", "0").strip().lower() in ("1", "true", "yes", "on")

TOPIC_MONITOR_EVENT = "monitor/+/event"
TOPIC_ROBOT_STATUS = "robot/+/status"
TOPIC_ROBOT_EVENT = "robot/+/event"
TOPIC_ROBOT_DETECTION_INFO = "robot/+/detection/info"
TOPIC_ROBOT_REQUEST = "robot/+/request"
TOPIC_MISSION_EVENT = "mission/+/event"
TOPIC_MISSION_STATE = "mission/+/state"
TOPIC_MISSION_STATUS = "mission/+/status"
TOPIC_FMS_MISSION_STATE = "fms/mission/+/state"

LANGUAGE_ALIASES = {
    "ko": "ko",
    "kor": "ko",
    "korean": "ko",
    "zh": "zh",
    "chi": "zh",
    "chinese": "zh",
    "ja": "ja",
    "jp": "ja",
    "japanese": "ja",
    "en": "en",
    "eng": "en",
    "english": "en",
}

ROBOT_EVENT_MAP = {
    "FIRE": db.EVENT_FIRE_DETECTED,
    "FIRE_DETECTED": db.EVENT_FIRE_DETECTED,
    "INJURED_PERSON": db.EVENT_EMERGENCY_PATIENT,
    "EMERGENCY_PATIENT": db.EVENT_EMERGENCY_PATIENT,
    "PATIENT": db.EVENT_EMERGENCY_PATIENT,
    "GUN": db.EVENT_THREAT_DETECTED,
    "KNIFE": db.EVENT_THREAT_DETECTED,
    "THREAT_GUN": db.EVENT_THREAT_DETECTED,
    "THREAT_KNIFE": db.EVENT_THREAT_DETECTED,
    "SUSPICIOUS_PERSON": db.EVENT_THREAT_DETECTED,
    "LOST_ITEM": db.EVENT_LOST_ITEM,
    "EMERGENCY_ACTION": db.EVENT_EMERGENCY_ACTION,
}

CLASS_EVENT_MAP = {
    "fire": db.EVENT_FIRE_DETECTED,
    "patient": db.EVENT_EMERGENCY_PATIENT,
    "pistol": db.EVENT_THREAT_DETECTED,
    "gun": db.EVENT_THREAT_DETECTED,
    "knife": db.EVENT_THREAT_DETECTED,
    "wallet": db.EVENT_LOST_ITEM,
    "bag": db.EVENT_LOST_ITEM,
    "phone": db.EVENT_LOST_ITEM,
}


def _mqtt_client_class():
    try:
        import paho.mqtt.client as mqtt
    except ModuleNotFoundError as exc:
        raise RuntimeError("paho-mqtt is required. Install it with: pip install paho-mqtt") from exc
    return mqtt


def normalize_language(value: str | None) -> str | None:
    if value is None:
        return None
    return LANGUAGE_ALIASES.get(str(value).strip().lower())


def topic_id(topic: str) -> str | None:
    parts = topic.split("/")
    return parts[1] if len(parts) >= 2 else None


def mission_id_from_topic(topic: str) -> str | None:
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0] == "fms" and parts[1] == "mission":
        return parts[2]
    if len(parts) >= 3 and parts[0] == "mission":
        return parts[1]
    return topic_id(topic)


def threat_type(payload: dict) -> str | None:
    value = payload.get("threat_type") or payload.get("detection_type") or payload.get("class")
    event_type = str(payload.get("event_type") or "").upper()
    if value is not None:
        value = str(value).strip().lower()
        if value == "pistol":
            value = "gun"
    elif "GUN" in event_type:
        value = "gun"
    elif "KNIFE" in event_type:
        value = "knife"
    return value if value in db.THREAT_TYPES else None


def detection_class(payload: dict) -> str | None:
    value = payload.get("class") or payload.get("detection_class") or payload.get("object_class")
    if value is None:
        return None
    return str(value).strip().lower()


def normalized_event_type(payload: dict) -> str | None:
    raw_type = str(payload.get("event_type") or "").upper()
    cls = detection_class(payload)
    return ROBOT_EVENT_MAP.get(raw_type) or (CLASS_EVENT_MAP.get(cls) if cls else None)


def location(payload: dict) -> tuple[int | None, str | None, str | None, float | None, float | None]:
    loc = payload.get("location") or {}
    pose = payload.get("pose") or {}
    if isinstance(loc.get("pose"), dict):
        pose = loc["pose"]

    floor = payload.get("floor") if payload.get("floor") is not None else loc.get("floor")
    zone = payload.get("zone") or loc.get("zone")
    location_name = (
        payload.get("location_name")
        or payload.get("location_label")
        or payload.get("place")
        or payload.get("poi_id")
        or loc.get("name")
        or loc.get("label")
        or loc.get("place")
        or loc.get("poi_id")
    )
    x = payload.get("x") if payload.get("x") is not None else loc.get("x")
    y = payload.get("y") if payload.get("y") is not None else loc.get("y")
    if x is None:
        x = pose.get("x")
    if y is None:
        y = pose.get("y")
    return floor, zone, location_name, x, y


def snapshot_ref(payload: dict) -> str | None:
    return (
        payload.get("snapshot_ref")
        or payload.get("image_ref")
        or payload.get("image_url")
        or payload.get("image_path")
        or payload.get("frame_ref")
        or payload.get("frame_url")
        or payload.get("screen_ref")
        or payload.get("screen_url")
    )


def customer(payload: dict) -> dict:
    value = payload.get("customer") or payload.get("customer_profile") or {}
    return value if isinstance(value, dict) else {}


class MqttJsonClient:
    def __init__(self) -> None:
        mqtt = _mqtt_client_class()
        self._mqtt = mqtt
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._handlers: dict[str, Callable[[str, dict], None]] = {}
        if MQTT_USER:
            self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        if MQTT_TLS:
            self.client.tls_set(
                ca_certs=MQTT_CA_CERT,
                certfile=MQTT_CERTFILE,
                keyfile=MQTT_KEYFILE,
                cert_reqs=ssl.CERT_REQUIRED if MQTT_CA_CERT else ssl.CERT_NONE,
            )
            self.client.tls_insecure_set(bool(MQTT_TLS_INSECURE or not MQTT_CA_CERT))

    def connect(self) -> None:
        logger.info("MQTT connecting to %s:%s", MQTT_HOST, MQTT_PORT)
        self.client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)

    def subscribe(self, topic_filter: str, handler: Callable[[str, dict], None], qos: int = 1) -> None:
        self._handlers[topic_filter] = handler
        self.client.message_callback_add(topic_filter, self._wrap(handler))
        self.client.subscribe(topic_filter, qos=qos)

    def loop_start(self) -> None:
        self.client.loop_start()

    def loop_stop(self) -> None:
        self.client.loop_stop()

    def disconnect(self) -> None:
        self.client.disconnect()

    def _wrap(self, handler: Callable[[str, dict], None]):
        def callback(_client, _userdata, msg) -> None:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                logger.warning("ignored non-JSON message topic=%s", msg.topic)
                return
            handler(msg.topic, payload)

        return callback

    def _on_connect(self, _client, _userdata, _flags, reason_code, _properties=None) -> None:
        if reason_code != 0:
            logger.error("MQTT connect failed: %s", reason_code)
            return
        logger.info("MQTT connected")
        for topic_filter in self._handlers:
            self.client.subscribe(topic_filter, qos=1)
            logger.info("subscribed %s", topic_filter)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties=None) -> None:
        logger.info("MQTT disconnected: %s", reason_code)


class DbBridge:
    def __init__(self) -> None:
        self.mqtt = MqttJsonClient()
        self.stop_event = threading.Event()

    def start(self) -> None:
        db.init_db()
        db.seed_default_robots()
        logger.info("SQLite ready: %s", db.DB_PATH)

        self.mqtt.connect()
        self.mqtt.subscribe(TOPIC_MONITOR_EVENT, self.on_monitor_event)
        self.mqtt.subscribe(TOPIC_ROBOT_STATUS, self.on_robot_status)
        self.mqtt.subscribe(TOPIC_ROBOT_EVENT, self.on_robot_event)
        self.mqtt.subscribe(TOPIC_ROBOT_DETECTION_INFO, self.on_robot_event)
        self.mqtt.subscribe(TOPIC_ROBOT_REQUEST, self.on_robot_request)
        self.mqtt.subscribe(TOPIC_MISSION_EVENT, self.on_mission_event)
        self.mqtt.subscribe(TOPIC_MISSION_STATE, self.on_mission_event)
        self.mqtt.subscribe(TOPIC_MISSION_STATUS, self.on_mission_event)
        self.mqtt.subscribe(TOPIC_FMS_MISSION_STATE, self.on_mission_event)
        self.mqtt.loop_start()
        logger.info("DB bridge ready")

    def save_event(self, topic: str, payload: dict, default_source_type: str = "mqtt") -> None:
        event_type = str(payload.get("event_type") or "").upper()
        mapped_event_type = normalized_event_type(payload)
        if mapped_event_type is not None:
            event_type = mapped_event_type
        if not event_type:
            logger.warning("event_type missing topic=%s payload=%s", topic, payload)
            return

        floor, zone, location_name, x, y = location(payload)
        event_id = db.record_monitor_event(
            event_type=event_type,
            source_type=payload.get("source_type") or default_source_type,
            source_id=payload.get("source_id") or topic_id(topic),
            robot_id=payload.get("robot_id"),
            mission_id=payload.get("mission_id"),
            language=normalize_language(payload.get("language") or customer(payload).get("language")),
            count=int(payload.get("count") or 1),
            detection_class=detection_class(payload),
            threat_type=threat_type(payload),
            action_type=payload.get("action_type"),
            floor=floor,
            zone=zone,
            location_name=location_name,
            x=x,
            y=y,
            confidence=payload.get("confidence"),
            snapshot_ref=snapshot_ref(payload),
            payload=payload,
            at=payload.get("timestamp") or payload.get("at"),
        )
        logger.info("saved event %s type=%s", event_id, event_type)

    def on_monitor_event(self, topic: str, payload: dict) -> None:
        self.save_event(topic, payload)

    def on_robot_status(self, topic: str, payload: dict) -> None:
        if not payload.get("robot_id"):
            payload = {**payload, "robot_id": topic_id(topic)}
        db.record_robot_status(payload)
        if payload.get("mission_id") and payload.get("mission_state"):
            db.upsert_mission(payload)
        logger.debug("saved robot status robot_id=%s", payload.get("robot_id"))

    def on_robot_event(self, topic: str, payload: dict) -> None:
        event_type = normalized_event_type(payload)
        if event_type is None:
            logger.warning("unknown robot event payload=%s", payload)
            return
        if not payload.get("robot_id"):
            payload = {**payload, "robot_id": topic_id(topic)}
        self.save_event(topic, {**payload, "event_type": event_type, "threat_type": threat_type(payload)}, "robot")

    def on_robot_request(self, topic: str, payload: dict) -> None:
        robot_id = payload.get("robot_id") or topic_id(topic)
        cust = customer(payload)
        language = normalize_language(payload.get("language") or cust.get("language"))
        common = {
            **payload,
            "source_type": "ui",
            "source_id": payload.get("source_id") or robot_id,
            "robot_id": robot_id,
            "language": language,
        }
        self.save_event(topic, {**common, "event_type": db.EVENT_USER_INTERACTION}, "ui")
        self.save_event(topic, {**common, "event_type": db.EVENT_ESCORT_STARTED}, "ui")
        weak = (
            payload.get("is_transportation_weak")
            or payload.get("transportation_weak")
            or cust.get("is_transportation_weak")
            or cust.get("transportation_weak")
        )
        if weak:
            self.save_event(topic, {**common, "event_type": db.EVENT_TRANSPORTATION_WEAK}, "ui")
        if payload.get("mission_id"):
            db.upsert_mission({**common, "mission_state": payload.get("mission_state") or "REQUESTED"})

    def on_mission_event(self, topic: str, payload: dict) -> None:
        mission_id = payload.get("mission_id") or mission_id_from_topic(topic)
        if mission_id and not payload.get("mission_id"):
            payload = {**payload, "mission_id": mission_id}
        if payload.get("mission_id"):
            db.upsert_mission(payload)
        event_type = str(payload.get("event_type") or payload.get("state") or "").upper()
        if event_type in ("COMPLETED", "MISSION_COMPLETED", "ESCORT_COMPLETED"):
            self.save_event(topic, {**payload, "event_type": db.EVENT_ESCORT_COMPLETED}, "mission")

    def stop(self) -> None:
        logger.info("DB bridge shutting down")
        self.mqtt.loop_stop()
        self.mqtt.disconnect()
        db.close()
        self.stop_event.set()

    def run_forever(self) -> None:
        self.start()
        signal.signal(signal.SIGINT, lambda *_: self.stop())
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        self.stop_event.wait()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    DbBridge().run_forever()


if __name__ == "__main__":
    main()
