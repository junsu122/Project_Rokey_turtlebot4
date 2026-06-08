"""Monitoring server entry point.

This process only observes incoming MQTT messages and serves the dashboard/API.
It does not create missions, publish robot tasks, or control robot behavior.
"""

from __future__ import annotations

import logging
import signal
import threading

import api
import config
import db
import event_service
from robot_registry import RobotRegistry
from transport import MqttTransport


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("monitor.main")


class MonitorServer:
    def __init__(self) -> None:
        self.transport = MqttTransport()
        self.registry = RobotRegistry()
        self._stop = threading.Event()

    def start(self) -> None:
        db.init_db()
        logger.info("SQLite ready (WAL): %s", config.DB_PATH)

        self.transport.connect()
        self.transport.loop_start()

        self.transport.subscribe(
            config.TOPIC_STATUS_WILDCARD, self._on_status, config.QOS_STATUS)
        self.transport.subscribe(
            config.TOPIC_EVENT_WILDCARD, self._on_event, config.QOS_EVENT)

        threading.Thread(
            target=api.run_api,
            args=(self.registry,),
            daemon=True,
            name="flask-api",
        ).start()

        logger.info("monitor server ready - status/event ingest + dashboard API")

    def _on_status(self, _topic: str, payload: dict) -> None:
        self.registry.update_from_status(payload)

    def _on_event(self, _topic: str, payload: dict) -> None:
        event_service.record_event(payload)

    def stop(self) -> None:
        logger.info("monitor server shutting down")
        self._stop.set()
        self.transport.loop_stop()
        self.transport.disconnect()
        db.close()

    def run_forever(self) -> None:
        self.start()
        signal.signal(signal.SIGINT, lambda *_: self.stop())
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        self._stop.wait()


def main() -> None:
    MonitorServer().run_forever()


if __name__ == "__main__":
    main()
