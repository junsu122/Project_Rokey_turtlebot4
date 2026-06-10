"""Monitoring server entry point.

This process only observes incoming ROS2 messages and serves the dashboard/API.
It does not create missions, publish robot tasks, or control robot behavior.
"""

from __future__ import annotations

import logging
import signal
import threading

import rclpy

import api
import config
import store
from ros_ingest import RosIngestNode
from robot_registry import RobotRegistry


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("monitor.main")


class MonitorServer:
    def __init__(self) -> None:
        self.registry = RobotRegistry()
        self.ros_node: RosIngestNode | None = None
        self._stopped = False

    def start(self) -> None:
        store.init()

        rclpy.init(args=None)
        self.ros_node = RosIngestNode(self.registry)

        # The Supabase backend is a write-only pump; the dashboard reads straight
        # from Supabase (Vercel), so the local Flask API is only started for the
        # local SQLite backend.
        if config.BACKEND == "supabase":
            logger.info("monitor server ready - ROS2 ingest -> Supabase (no local API)")
        else:
            threading.Thread(
                target=api.run_api,
                args=(self.registry,),
                daemon=True,
                name="flask-api",
            ).start()
            logger.info("monitor server ready - ROS2 ingest + dashboard API")

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        logger.info("monitor server shutting down")
        if self.ros_node is not None:
            try:
                self.ros_node.destroy_node()
            except Exception as exc:  # rclpy destroy_node can raise on teardown
                logger.warning("ros node teardown: %s", exc)
            self.ros_node = None
        if rclpy.ok():
            rclpy.shutdown()
        store.close()

    def run_forever(self) -> None:
        self.start()
        signal.signal(signal.SIGINT, lambda *_: rclpy.shutdown())
        signal.signal(signal.SIGTERM, lambda *_: rclpy.shutdown())
        try:
            if self.ros_node is not None:
                rclpy.spin(self.ros_node)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main() -> None:
    MonitorServer().run_forever()


if __name__ == "__main__":
    main()
