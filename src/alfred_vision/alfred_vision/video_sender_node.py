#!/usr/bin/env python3
"""video_sender_node — 카메라 라이브 영상 WebRTC 송신 (데이터 평면, FMS/브리지 우회).

설계(아키텍처 다이어그램·bridge_config 주석):
  영상은 제어 평면(FMS/MQTT)을 거치지 않는다. 로봇이 직접 브라우저(관리자 UI)와
  WebRTC P2P 연결을 맺고, FMS는 시그널링 URL 메타데이터만 제공한다.

동작:
  ▼ subs : <image_topic>  (sensor_msgs/CompressedImage, JPEG)
  → aiortc 비디오 트랙으로 인코딩(VP8) → 브라우저로 P2P 송신
  시그널링: 이 노드가 직접 띄우는 HTTP 서버  POST /offer  (SDP offer→answer)

파라미터:
  image_topic (str)  기본 '/camera/image_raw/compressed' — 로봇별로 지정
                     예) robot2/oakd/rgb/image_raw/compressed
  http_host  (str)   기본 '0.0.0.0'
  http_port  (int)   기본 8081
  fps        (int)   기본 20 (송신 프레임률 상한)

의존성(로봇에 설치): aiortc, aiohttp, numpy, opencv-python  (av 는 aiortc 가 끌어옴)
  pip install aiortc aiohttp opencv-python numpy
"""
from __future__ import annotations

import asyncio
import logging
import threading

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

try:
    import cv2
    import av
    from aiohttp import web
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
except ImportError as e:  # 로봇에 의존성 미설치 시 명확히 안내하고 종료
    raise SystemExit(
        f"WebRTC 의존성 누락: {e}\n"
        "  pip install aiortc aiohttp opencv-python numpy"
    )

logger = logging.getLogger("video_sender")

# CORS: 대시보드(다른 출처)에서 fetch 하므로 허용. LAN 데모 기준 와일드카드.
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class FrameHolder:
    """ROS 콜백(ROS 스레드)이 최신 프레임을 쓰고, 트랙(asyncio)이 읽는 공유 버퍼."""

    def __init__(self) -> None:
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()

    def set(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame

    def get(self) -> np.ndarray | None:
        with self._lock:
            return self._frame


class RosVideoTrack(VideoStreamTrack):
    """holder 의 최신 BGR 프레임을 aiortc 비디오 트랙으로 송출. 30fps 페이싱은 base 제공."""

    def __init__(self, holder: FrameHolder) -> None:
        super().__init__()
        self.holder = holder
        self._blank = np.zeros((480, 640, 3), dtype=np.uint8)

    async def recv(self):
        pts, time_base = await self.next_timestamp()  # VideoStreamTrack 기본 페이싱
        frame = self.holder.get()
        if frame is None:
            frame = self._blank
        vf = av.VideoFrame.from_ndarray(frame, format="bgr24")
        vf.pts = pts
        vf.time_base = time_base
        return vf


class VideoSenderNode(Node):
    def __init__(self) -> None:
        super().__init__("video_sender_node")
        self.declare_parameter("image_topic", "/camera/image_raw/compressed")
        self.declare_parameter("http_host", "0.0.0.0")
        self.declare_parameter("http_port", 8081)
        self.declare_parameter("fps", 20)

        self.topic = self.get_parameter("image_topic").value
        self.http_host = self.get_parameter("http_host").value
        self.http_port = int(self.get_parameter("http_port").value)

        self.holder = FrameHolder()
        self._frames = 0
        self.create_subscription(CompressedImage, self.topic, self._on_image, 5)
        self.get_logger().info(
            f"video_sender_node 시작 · 토픽={self.topic} · "
            f"시그널링 http://{self.http_host}:{self.http_port}/offer"
        )

    def _on_image(self, msg: CompressedImage) -> None:
        # JPEG 바이트 → BGR ndarray (cv_bridge 불필요)
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is not None:
            self.holder.set(img)
            self._frames += 1
            if self._frames % 100 == 0:
                self.get_logger().info(
                    f"수신 프레임 {self._frames} · {img.shape[1]}x{img.shape[0]}")


# ── 시그널링 HTTP 서버 (aiohttp, asyncio 루프) ─────────────────────────────
pcs: set = set()


async def _offer(request: "web.Request") -> "web.Response":
    holder: FrameHolder = request.app["holder"]
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def _on_state() -> None:
        logger.info("peer state: %s", pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            pcs.discard(pc)

    pc.addTrack(RosVideoTrack(holder))
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
        headers=CORS,
    )


async def _options(request: "web.Request") -> "web.Response":
    return web.Response(headers=CORS)


async def _health(request: "web.Request") -> "web.Response":
    return web.json_response({"status": "ok", "peers": len(pcs)}, headers=CORS)


async def _on_shutdown(app: "web.Application") -> None:
    await asyncio.gather(*[pc.close() for pc in list(pcs)], return_exceptions=True)
    pcs.clear()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VideoSenderNode()

    # ROS 스핀은 별도 스레드(콜백에서 프레임만 적재). 시그널링/미디어는 메인 asyncio 루프.
    spin = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin.start()

    app = web.Application()
    app["holder"] = node.holder
    app.router.add_post("/offer", _offer)
    app.router.add_options("/offer", _options)
    app.router.add_get("/health", _health)
    app.on_shutdown.append(_on_shutdown)

    try:
        web.run_app(app, host=node.http_host, port=node.http_port, print=None)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
