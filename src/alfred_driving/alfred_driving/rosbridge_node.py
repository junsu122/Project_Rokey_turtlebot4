#!/usr/bin/env python3
"""Minimal rosbridge-compatible websocket inlet for web escort requests.

This node accepts text websocket messages shaped like rosbridge publish
commands and republishes them to /information as std_msgs/String:

    {"op": "publish", "topic": "/information", "msg": {...}}

Only the small surface needed by web_request_node is implemented. It is not a
drop-in replacement for rosbridge_suite.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import socketserver
import struct
import threading
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME_BYTES = 1024 * 1024


class _ThreadingWebsocketServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls, bridge_node: "RosbridgeNode"):
        super().__init__(server_address, handler_cls)
        self.bridge_node = bridge_node


class _RosbridgeHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        if not self._handshake():
            return

        self.server.bridge_node.get_logger().info(
            f"rosbridge client connected: {self.client_address[0]}:{self.client_address[1]}"
        )

        while rclpy.ok():
            try:
                opcode, payload = self._read_frame()
            except (ConnectionError, OSError, ValueError) as err:
                self.server.bridge_node.get_logger().debug(f"websocket closed: {err}")
                return

            if opcode == 0x8:  # close
                self._send_frame(b"", opcode=0x8)
                return
            if opcode == 0x9:  # ping
                self._send_frame(payload, opcode=0xA)
                continue
            if opcode != 0x1:  # text only
                continue

            try:
                message = payload.decode("utf-8")
            except UnicodeDecodeError:
                self._send_json({"op": "error", "msg": "payload is not utf-8"})
                continue

            response = self.server.bridge_node.handle_rosbridge_message(message)
            if response is not None:
                self._send_json(response)

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

        accept = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        self.request.sendall(response.encode("ascii"))
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

    def _send_json(self, payload: dict[str, Any]) -> None:
        self._send_frame(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _send_frame(self, payload: bytes, opcode: int = 0x1) -> None:
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", first, length)
        elif length < 65536:
            header = struct.pack("!BBH", first, 126, length)
        else:
            header = struct.pack("!BBQ", first, 127, length)
        self.request.sendall(header + payload)


class RosbridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("rosbridge_node")

        self.declare_parameter("host", "0.0.0.0")
        self.declare_parameter("port", 9090)
        self.declare_parameter("topic", "/information")

        self.host = self.get_parameter("host").value
        self.port = int(self.get_parameter("port").value)
        self.topic = self.get_parameter("topic").value
        self.publisher = self.create_publisher(String, self.topic, 10)

        self._server = _ThreadingWebsocketServer((self.host, self.port), _RosbridgeHandler, self)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        self.get_logger().info(f"rosbridge websocket listening on ws://{self.host}:{self.port}")
        self.get_logger().info(f"Publishing rosbridge messages to {self.topic}")

    def handle_rosbridge_message(self, raw: str) -> dict[str, Any] | None:
        try:
            envelope = json.loads(raw)
        except ValueError as err:
            self.get_logger().warn(f"Ignoring non-JSON websocket message: {err}")
            return {"op": "error", "msg": "message is not valid JSON"}

        op = envelope.get("op")
        if op in ("advertise", "unadvertise"):
            return None
        if op != "publish":
            return {"op": "error", "msg": f"unsupported op: {op}"}
        if envelope.get("topic") != self.topic:
            return {"op": "error", "msg": f"unsupported topic: {envelope.get('topic')}"}
        if "msg" not in envelope:
            return {"op": "error", "msg": "publish message is missing msg"}

        msg = String()
        msg.data = json.dumps(envelope, ensure_ascii=False)
        self.publisher.publish(msg)
        self.get_logger().info(f"Published web request to {self.topic}")
        return None

    def destroy_node(self) -> bool:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1.0)
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RosbridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
