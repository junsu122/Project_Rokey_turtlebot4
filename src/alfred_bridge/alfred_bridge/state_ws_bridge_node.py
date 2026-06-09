#!/usr/bin/env python3
"""state_ws_bridge_node — driving state 변경을 WebSocket으로 web에 push.

구독 토픽 (alfred_driving 직접):
  /robot2/nav_status  (std_msgs/String) — "patrol_stopped", "arrived" 등
  /robot4/nav_status  (std_msgs/String)
  /escort_state       (alfred_interfaces/msg/RobotState) — escort_state_bridge_node 발행

state가 바뀔 때만 연결된 모든 web 클라이언트에 broadcast한다.

push 메시지 형식 (rosbridge_node envelope 호환):
  {"op": "publish", "topic": "<topic>", "msg": <payload>}

실행:
  ros2 run alfred_bridge state_ws_bridge_node --ros-args -p port:=9091
"""
from __future__ import annotations

import base64
import hashlib
import json
import socketserver
import struct
import threading
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from alfred_interfaces.msg import RobotState


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME_BYTES = 1024 * 1024


class _ThreadingWebsocketServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls, bridge_node: "StateWsBridgeNode"):
        super().__init__(server_address, handler_cls)
        self.bridge_node = bridge_node
        self._clients_lock = threading.Lock()
        self._clients: set["_BroadcastHandler"] = set()

    def register(self, handler: "_BroadcastHandler") -> None:
        with self._clients_lock:
            self._clients.add(handler)

    def unregister(self, handler: "_BroadcastHandler") -> None:
        with self._clients_lock:
            self._clients.discard(handler)

    def broadcast_json(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        with self._clients_lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.send_text(text)
            except (ConnectionError, OSError) as err:
                self.bridge_node.get_logger().debug(f"broadcast 실패: {err}")


class _BroadcastHandler(socketserver.BaseRequestHandler):
    """push 전용 채널 — 클라이언트가 보내는 프레임은 ping/close만 응답하고 버린다."""

    def setup(self) -> None:
        self._send_lock = threading.Lock()

    def handle(self) -> None:
        if not self._handshake():
            return
        self.server.bridge_node.get_logger().info(
            f"web client connected: {self.client_address[0]}:{self.client_address[1]}"
        )
        self.server.register(self)
        try:
            while rclpy.ok():
                try:
                    opcode, payload = self._read_frame()
                except (ConnectionError, OSError, ValueError) as err:
                    self.server.bridge_node.get_logger().debug(f"websocket closed: {err}")
                    return
                if opcode == 0x8:
                    self._send_frame(b"", opcode=0x8)
                    return
                if opcode == 0x9:
                    self._send_frame(payload, opcode=0xA)
        finally:
            self.server.unregister(self)

    def send_text(self, text: str) -> None:
        self._send_frame(text.encode("utf-8"))

    def _handshake(self) -> bool:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.request.recv(4096)
            if not chunk:
                return False
            data += chunk
            if len(data) > 16384:
                return False
        try:
            header_text = data.decode("iso-8859-1")
        except UnicodeDecodeError:
            return False
        lines = header_text.split("\r\n")
        if not lines or "websocket" not in header_text.lower():
            return False
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        key = headers.get("sec-websocket-key")
        if not key:
            return False
        accept = base64.b64encode(
            hashlib.sha1((key + GUID).encode("ascii")).digest()
        ).decode("ascii")
        self.request.sendall((
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        ).encode("ascii"))
        return True

    def _read_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self.request.recv(size - len(data))
            if not chunk:
                raise ConnectionError("client disconnected")
            data += chunk
        return data

    def _read_frame(self) -> tuple[int, bytes]:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if length > MAX_FRAME_BYTES:
            raise ValueError("frame too large")
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        return opcode, payload

    def _send_frame(self, payload: bytes, opcode: int = 0x1) -> None:
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", first, length)
        elif length < 65536:
            header = struct.pack("!BBH", first, 126, length)
        else:
            header = struct.pack("!BBQ", first, 127, length)
        with self._send_lock:
            self.request.sendall(header + payload)


class StateWsBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("state_ws_bridge_node")

        self.declare_parameter("host", "0.0.0.0")
        self.declare_parameter("port", 9091)

        host = self.get_parameter("host").value
        port = int(self.get_parameter("port").value)

        # 직전 상태 캐시 — 바뀐 경우에만 broadcast
        self._last: dict[str, str] = {}

        self._server = _ThreadingWebsocketServer((host, port), _BroadcastHandler, self)
        self._ws_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._ws_thread.start()

        self.create_subscription(String, "/robot2/nav_status", self._cb_r2, 10)
        self.create_subscription(String, "/robot4/nav_status", self._cb_r4, 10)
        self.create_subscription(RobotState, "/escort_state", self._cb_escort, 10)

        self.get_logger().info(f"state_ws_bridge: ws://{host}:{port} 에서 web 연결 대기")

    # ── ROS 콜백 ──────────────────────────────────────────────────────────────

    def _cb_r2(self, msg: String) -> None:
        self._push_if_changed("/robot2/nav_status", msg.data, {"data": msg.data})

    def _cb_r4(self, msg: String) -> None:
        self._push_if_changed("/robot4/nav_status", msg.data, {"data": msg.data})

    def _cb_escort(self, msg: RobotState) -> None:
        self._push_if_changed("/escort_state", msg.state, {
            "robot_id":       msg.robot_id,
            "state":          msg.state,
            "current_task_id": msg.current_task_id,
            "task_status":    msg.task_status,
            "battery":        msg.battery,
            "timestamp":      msg.timestamp,
        })

    def _push_if_changed(self, topic: str, key: str, payload: dict) -> None:
        if self._last.get(topic) == key:
            return
        self._last[topic] = key
        self.get_logger().info(f"[{topic}] → {key} — web push")
        self._server.broadcast_json({"op": "publish", "topic": topic, "msg": payload})

    def destroy_node(self) -> bool:
        self._server.shutdown()
        self._server.server_close()
        self._ws_thread.join(timeout=1.0)
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = StateWsBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
