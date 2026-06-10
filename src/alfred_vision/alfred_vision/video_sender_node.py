#!/usr/bin/env python3
"""
WebRTC video sender node.

Subscribes to /{namespace}/detection/image and serves it as a VP8 WebRTC stream.
Browser (recvonly) sends SDP offer to POST /offer, receives non-trickle answer.

Usage:
  ros2 run alfred_vision video_sender --ros-args \
    -p namespace:=/robot2 -p signal_port:=8081
"""
import asyncio
import json
import threading
from fractions import Fraction

import av
import cv2
import numpy as np
import rclpy
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage


class _RosVideoTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._bgr  = None
        self._lock = threading.Lock()
        self._pts  = 0

    def push(self, bgr: np.ndarray):
        with self._lock:
            self._bgr = bgr.copy()

    async def recv(self) -> VideoFrame:
        await asyncio.sleep(1 / 30)
        with self._lock:
            bgr = self._bgr

        if bgr is None:
            bgr = np.zeros((480, 640, 3), dtype=np.uint8)

        rgb          = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        vf           = VideoFrame.from_ndarray(rgb, format="rgb24")
        vf.pts       = self._pts
        vf.time_base = Fraction(1, 90000)
        self._pts   += 3000  # 90000 / 30fps
        return vf


class VideoSenderNode(Node):
    def __init__(self):
        super().__init__('video_sender')

        self.declare_parameter('namespace',   '/robot2')
        self.declare_parameter('signal_port', 8081)

        ns   = self.get_parameter('namespace').value.strip()
        port = self.get_parameter('signal_port').value

        self._track = _RosVideoTrack()
        self._pcs   = set()

        self.create_subscription(CompressedImage, ns, self._cb_image, 1)
        self.get_logger().info(f'[{ns}] video_sender 시작 — port {port}')

        self._loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run_server, args=(port,), daemon=True)
        t.start()

    # ── ROS callback ──────────────────────────────────────────────────────────

    def _cb_image(self, msg: CompressedImage):
        np_arr = np.frombuffer(msg.data, np.uint8)
        bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if bgr is not None:
            self._track.push(bgr)

    # ── HTTP signaling server ─────────────────────────────────────────────────

    def _run_server(self, port: int):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve(port))

    async def _serve(self, port: int):
        app = web.Application()
        app.router.add_options('/offer',  self._handle_cors)
        app.router.add_post  ('/offer',   self._handle_offer)
        app.router.add_get   ('/health',  self._handle_health)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        await asyncio.Event().wait()  # run forever

    @staticmethod
    def _cors(resp: web.Response) -> web.Response:
        resp.headers['Access-Control-Allow-Origin']  = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    async def _handle_cors(self, request: web.Request) -> web.Response:
        return self._cors(web.Response(status=200))

    async def _handle_health(self, request: web.Request) -> web.Response:
        return self._cors(web.json_response({'status': 'ok', 'peers': len(self._pcs)}))

    async def _handle_offer(self, request: web.Request) -> web.Response:
        body  = await request.json()
        offer = RTCSessionDescription(sdp=body['sdp'], type=body['type'])

        pc = RTCPeerConnection()
        self._pcs.add(pc)

        @pc.on('connectionstatechange')
        async def on_state():
            if pc.connectionState in ('failed', 'closed'):
                await pc.close()
                self._pcs.discard(pc)

        await pc.setRemoteDescription(offer)
        pc.addTrack(self._track)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # non-trickle: ICE 수집 완료 대기 후 answer 반환
        ice_done = asyncio.Event()

        @pc.on('icegatheringstatechange')
        def on_ice():
            if pc.iceGatheringState == 'complete':
                ice_done.set()

        if pc.iceGatheringState != 'complete':
            await asyncio.wait_for(ice_done.wait(), timeout=10.0)

        resp = web.json_response({
            'sdp':  pc.localDescription.sdp,
            'type': pc.localDescription.type,
        })
        return self._cors(resp)


def main(args=None):
    rclpy.init(args=args)
    node = VideoSenderNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
