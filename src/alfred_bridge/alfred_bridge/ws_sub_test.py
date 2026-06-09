#!/usr/bin/env python3
"""rosbridge websocket 구독 테스트 — /test_topic 메시지를 받으면 출력."""
import json
import websocket

ws = websocket.create_connection("ws://localhost:9090")
ws.send(json.dumps({"op": "subscribe", "topic": "/test_topic", "type": "std_msgs/String"}))
print("subscribed. waiting for messages... (Ctrl+C to stop)")

while True:
    print(ws.recv())
