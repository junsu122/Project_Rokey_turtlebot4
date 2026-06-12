#!/usr/bin/env python3
"""웹 안내 요청과 상태 구독을 위한 최소 rosbridge 호환 websocket 노드.

이 노드는 rosbridge publish 명령 형태의 text websocket 메시지를 받아
/information 토픽으로 std_msgs/String 형태로 다시 발행한다.

    {"op": "publish", "topic": "/information", "msg": {...}}

또한 kiosk가 같은 websocket으로 /robot2/ui_state 같은 String 토픽을
구독할 수 있도록 subscribe/unsubscribe 일부를 지원한다.

server_request_node와 kiosk에 필요한 최소 기능만 구현되어 있으며,
rosbridge_suite를 완전히 대체하는 노드는 아니다.
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
    """여러 websocket client를 thread로 동시에 처리하는 TCP 서버.

    Python 표준 라이브러리의 TCPServer를 사용하되, ThreadingMixIn을 섞어서
    client 하나가 연결되어 있어도 다른 client 연결을 막지 않게 한다.
    `bridge_node`는 실제 ROS publisher와 logger를 가진 RosbridgeNode 객체다.
    """

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls, bridge_node: "RosbridgeNode"):
        """서버 주소, handler class, ROS bridge node 참조를 저장한다."""
        super().__init__(server_address, handler_cls)
        self.bridge_node = bridge_node


class _RosbridgeHandler(socketserver.BaseRequestHandler):
    """client 연결 하나를 담당하는 websocket handler.

    이 클래스는 HTTP websocket handshake, websocket frame 읽기/쓰기,
    ping/close/text opcode 처리를 담당한다. 실제 ROS 토픽 발행 판단은
    RosbridgeNode.handle_rosbridge_message()에 위임한다.
    """

    def setup(self) -> None:
        self._send_lock = threading.Lock()
        self._subscriptions: set[str] = set()

    def finish(self) -> None:
        for topic in list(self._subscriptions):
            self.server.bridge_node.unsubscribe_client(topic, self)

    def handle(self) -> None:
        """client 연결의 전체 생명주기를 처리한다.

        1. websocket handshake 수행
        2. frame을 반복해서 읽음
        3. close/ping/text frame을 구분
        4. text frame이면 JSON 문자열로 해석해서 RosbridgeNode에 전달
        5. 에러 응답이 있으면 websocket으로 다시 전송
        """
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

            if opcode == 0x8:  # 연결 종료 프레임
                self._send_frame(b"", opcode=0x8)
                return
            if opcode == 0x9:  # ping 프레임
                self._send_frame(payload, opcode=0xA)
                continue
            if opcode != 0x1:  # text 프레임만 처리
                continue

            try:
                message = payload.decode("utf-8")
            except UnicodeDecodeError:
                self._send_json({"op": "error", "msg": "payload is not utf-8"})
                continue

            response = self.server.bridge_node.handle_rosbridge_message(message, self)
            if response is not None:
                self._send_json(response)

    def _handshake(self) -> bool:
        """HTTP Upgrade 요청을 websocket 연결로 전환한다.

        websocket은 처음에 일반 HTTP 요청처럼 시작하고, `Sec-WebSocket-Key`를
        서버가 GUID와 조합해 `Sec-WebSocket-Accept`를 만들어 응답해야 연결이
        성립한다. 성공하면 True, 형식이 이상하면 False를 반환한다.
        """
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
        """socket에서 정확히 size byte를 읽는다.

        recv()는 요청한 길이보다 적게 반환할 수 있으므로, 원하는 길이를 다 받을
        때까지 반복한다. 중간에 연결이 끊기면 ConnectionError를 발생시킨다.
        """
        data = b""
        while len(data) < size:
            chunk = self.request.recv(size - len(data))
            if not chunk:
                raise ConnectionError("client disconnected")
            data += chunk
        return data

    def _read_frame(self) -> tuple[int, bytes]:
        """websocket frame 하나를 읽어서 opcode와 payload를 반환한다.

        처리 내용:
        - frame header에서 opcode, mask 여부, payload 길이 추출
        - payload 길이가 126/127이면 확장 길이 필드까지 읽음
        - client frame은 masking되어 있으므로 mask를 적용해 원본 payload 복원
        - 너무 큰 frame은 메모리 보호를 위해 거부
        """
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
        """dict payload를 JSON text frame으로 client에게 전송한다."""
        self._send_frame(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def subscribe(self, topic: str) -> None:
        self._subscriptions.add(topic)

    def unsubscribe(self, topic: str) -> None:
        self._subscriptions.discard(topic)

    def _send_frame(self, payload: bytes, opcode: int = 0x1) -> None:
        """websocket frame을 만들어 socket으로 전송한다.

        서버에서 client로 보내는 frame은 masking하지 않는다. payload 길이에 따라
        websocket 규격의 짧은 길이/16bit 길이/64bit 길이 header를 선택한다.
        기본 opcode `0x1`은 text frame이다.
        """
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


class RosbridgeNode(Node):
    """websocket 입력을 ROS `/information` 토픽으로 변환하는 ROS 노드."""

    def __init__(self) -> None:
        """ROS publisher와 websocket 서버 thread를 초기화한다.

        parameter:
        - `host`: websocket 서버가 bind할 주소
        - `port`: websocket 서버 port
        - `topic`: 허용할 rosbridge publish topic. 기본 `/information`
        """
        super().__init__("rosbridge_node")

        self.declare_parameter("host", "0.0.0.0")
        self.declare_parameter("port", 9090)
        self.declare_parameter("topic", "/information")

        self.host = self.get_parameter("host").value
        self.port = int(self.get_parameter("port").value)
        self.topic = self.get_parameter("topic").value
        self.publisher = self.create_publisher(String, self.topic, 10)
        self._sub_lock = threading.Lock()
        self._clients_by_topic: dict[str, set[_RosbridgeHandler]] = {}
        self._subscriptions: dict[str, Any] = {}

        self._server = _ThreadingWebsocketServer((self.host, self.port), _RosbridgeHandler, self)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        self.get_logger().info(f"rosbridge websocket listening on ws://{self.host}:{self.port}")
        self.get_logger().info(f"Publishing rosbridge messages to {self.topic}")

    def handle_rosbridge_message(
        self,
        raw: str,
        client: _RosbridgeHandler,
    ) -> dict[str, Any] | None:
        """rosbridge 형식 JSON 문자열을 검증하고 ROS 토픽으로 발행한다.

        허용하는 메시지는 다음 형식뿐이다.

        ```json
        {"op": "publish", "topic": "/information", "msg": {...}}
        ```

        `advertise`와 `unadvertise`는 웹 client 호환을 위해 조용히 무시한다.
        `subscribe`와 `unsubscribe`는 std_msgs/String 계열 토픽만 간단히 중계한다.
        그 외 잘못된 메시지는 websocket client에게 보낼 error dict를 반환한다.
        정상 publish는 `/information`으로 발행하고 None을 반환한다.
        """
        try:
            envelope = json.loads(raw)
        except ValueError as err:
            self.get_logger().warn(f"Ignoring non-JSON websocket message: {err}")
            return {"op": "error", "msg": "message is not valid JSON"}

        op = envelope.get("op")
        if op in ("advertise", "unadvertise"):
            return None
        if op == "subscribe":
            topic = envelope.get("topic")
            if not isinstance(topic, str) or not topic:
                return {"op": "error", "msg": "subscribe topic is missing"}
            self.subscribe_client(topic, client)
            return None
        if op == "unsubscribe":
            topic = envelope.get("topic")
            if not isinstance(topic, str) or not topic:
                return {"op": "error", "msg": "unsubscribe topic is missing"}
            self.unsubscribe_client(topic, client)
            return None
        if op != "publish":
            return {"op": "error", "msg": f"unsupported op: {op}"}
        if envelope.get("topic") != self.topic:
            return {"op": "error", "msg": f"unsupported topic: {envelope.get('topic')}"}
        if "msg" not in envelope:
            return {"op": "error", "msg": "publish message is missing msg"}

        payload = normalize_rosbridge_msg(envelope["msg"])
        if payload is None:
            return {"op": "error", "msg": "publish msg is empty or invalid"}

        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.publisher.publish(msg)
        self.get_logger().info(f"Published web request to {self.topic}")
        return None

    def subscribe_client(self, topic: str, client: _RosbridgeHandler) -> None:
        """Register one websocket client for a String ROS topic."""
        with self._sub_lock:
            self._clients_by_topic.setdefault(topic, set()).add(client)
            client.subscribe(topic)
            if topic not in self._subscriptions:
                self._subscriptions[topic] = self.create_subscription(
                    String,
                    topic,
                    lambda msg, t=topic: self._forward_string_topic(t, msg),
                    10,
                )
        self.get_logger().info(f"websocket subscribed to {topic}")

    def unsubscribe_client(self, topic: str, client: _RosbridgeHandler) -> None:
        with self._sub_lock:
            clients = self._clients_by_topic.get(topic)
            if clients is None:
                return
            clients.discard(client)
            client.unsubscribe(topic)
            if not clients:
                self._clients_by_topic.pop(topic, None)
                sub = self._subscriptions.pop(topic, None)
                if sub is not None:
                    self.destroy_subscription(sub)
        self.get_logger().info(f"websocket unsubscribed from {topic}")

    def _forward_string_topic(self, topic: str, msg: String) -> None:
        frame = {
            "op": "publish",
            "topic": topic,
            "msg": {"data": msg.data},
        }
        with self._sub_lock:
            clients = list(self._clients_by_topic.get(topic, ()))
        for client in clients:
            try:
                client._send_json(frame)
            except OSError as err:
                self.get_logger().debug(f"failed to forward {topic}: {err}")

    def destroy_node(self) -> bool:
        """노드 종료 시 websocket 서버와 thread를 정리한다."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1.0)
        return super().destroy_node()


def normalize_rosbridge_msg(value: Any) -> dict[str, Any] | None:
    """Convert rosbridge msg payloads into the IF-01 dict used by /information.

    The frontend usually publishes std_msgs/String as {"data": "{...json...}"}.
    Direct structured payloads are also accepted.
    """
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, str):
            try:
                decoded = json.loads(data)
            except ValueError:
                return {"data": data}
            return decoded if isinstance(decoded, dict) else {"data": decoded}
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return {"data": value}
        return decoded if isinstance(decoded, dict) else {"data": decoded}
    return None


def main(args=None) -> None:
    """rosbridge_node 실행 진입점."""
    rclpy.init(args=args)
    node = RosbridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
