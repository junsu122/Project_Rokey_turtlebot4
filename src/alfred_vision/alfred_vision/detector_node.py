#!/usr/bin/env python3
import json
import math
import time
import uuid
import threading
import numpy as np
from datetime import datetime, timezone

import cv2
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import Image, CompressedImage, CameraInfo
from std_msgs.msg import String
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener
import tf2_geometry_msgs
from cv_bridge import CvBridge
from message_filters import Subscriber, ApproximateTimeSynchronizer

from alfred_vision.vision_resource import (
    DEFAULT_MODEL, CONF_THRESH, CONF_MAP, SNAPSHOT_DIR, DEPTH_PATCH,
    ROBOT_ID_MAP, FLOOR_MAP, EVENT_TYPE_MAP, EVENT_COLOR,
    DOCK_POSITIONS, DOCK_RADIUS,
)


class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector')

        self.declare_parameter('model_path', DEFAULT_MODEL)
        self.declare_parameter('conf',       CONF_THRESH)
        self.declare_parameter('namespace',  '/robot2')

        model_path = self.get_parameter('model_path').value
        self.conf  = self.get_parameter('conf').value
        self.ns    = self.get_parameter('namespace').value.strip()

        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

        self.get_logger().info(f'모델 로드 중: {model_path}')
        from ultralytics import YOLO
        self.model  = YOLO(model_path)
        self.bridge = CvBridge()
        self.get_logger().info(f'모델 로드 완료. 클래스: {self.model.names}')

        self.tf_buffer   = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # OAK-D는 BEST_EFFORT QoS로 publish — 맞춰줘야 수신 가능
        qos_be = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)

        self._lock            = threading.Lock()
        self._K               = None
        self._depth           = None
        self._camera_frame    = None
        self._first_frame     = True
        self._last_infer_time = 0.0

        self._confirm_counts = {}
        self._active_events  = {}

        self.create_subscription(
            CameraInfo,
            f'{self.ns}/oakd/rgb/camera_info',
            self._cb_camera_info,
            1,
        )

        rgb_sub   = Subscriber(self, CompressedImage,
                               f'{self.ns}/oakd/rgb/image_raw/compressed',
                               qos_profile=qos_be)
        depth_sub = Subscriber(self, CompressedImage,
                               f'{self.ns}/oakd/stereo/image_raw/compressedDepth',
                               qos_profile=qos_be)
        ts = ApproximateTimeSynchronizer([rgb_sub, depth_sub], queue_size=10, slop=0.1)
        ts.registerCallback(self._cb_synced)

        self._pub_event = self.create_publisher(String, f'{self.ns}/detection/info',  10)
        self._pub_img   = self.create_publisher(Image,  f'{self.ns}/detection/image', 10)

        self.get_logger().info(f'[{self.ns}] 구독/퍼블리시 설정 완료')

    def _cb_camera_info(self, msg: CameraInfo):
        with self._lock:
            if self._K is None:
                self._K = np.array(msg.k).reshape(3, 3)
                self.get_logger().info(
                    f'[{self.ns}] K 행렬 수신: fx={self._K[0,0]:.1f}, fy={self._K[1,1]:.1f}')

    def _cb_synced(self, rgb_msg: CompressedImage, depth_msg: CompressedImage):
        now = time.monotonic()
        if now - self._last_infer_time < 1.0:
            return
        self._last_infer_time = now

        try:
            buf   = np.frombuffer(rgb_msg.data, dtype=np.uint8)
            frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)

            # compressedDepth 포맷: 앞 12바이트는 헤더 → 제거 후 디코드
            depth_arr = np.frombuffer(bytes(depth_msg.data)[12:], dtype=np.uint8)
            depth = cv2.imdecode(depth_arr, cv2.IMREAD_ANYDEPTH)

            if frame is None or depth is None:
                return
            if self._first_frame:
                self._first_frame = False
                self.get_logger().info(f'[{self.ns}] 첫 프레임 수신 → YOLO 추론 시작')
            with self._lock:
                self._depth        = depth
                self._camera_frame = depth_msg.header.frame_id

            # 독 근접 시 추론 스킵 — 충전/도킹 중 오탐 방지
            if self._near_dock():
                return

            self._process(frame, rgb_msg.header)
        except Exception as e:
            self.get_logger().error(f'[{self.ns}] 동기화 콜백 오류: {e}')

    def _near_dock(self) -> bool:
        dock_pos = DOCK_POSITIONS.get(self.ns)
        if dock_pos is None:
            return False
        try:
            t  = self.tf_buffer.lookup_transform('map', 'base_link', Time(), timeout=Duration(seconds=0.3))
            rx = t.transform.translation.x
            ry = t.transform.translation.y
            return math.hypot(rx - dock_pos[0], ry - dock_pos[1]) < DOCK_RADIUS
        except Exception:
            return False

    def _depth_at(self, depth: np.ndarray, u: int, v: int) -> float:
        h, w = depth.shape[:2]
        v0, v1 = max(0, v - DEPTH_PATCH), min(h, v + DEPTH_PATCH + 1)
        u0, u1 = max(0, u - DEPTH_PATCH), min(w, u + DEPTH_PATCH + 1)
        patch = depth[v0:v1, u0:u1].astype(np.float32)
        valid = patch[patch > 0]
        if valid.size == 0:
            return 0.0
        return float(np.median(valid)) / 1000.0

    def _to_map(self, X: float, Y: float, Z: float, frame_id: str):
        pt = PointStamped()
        pt.header.stamp    = Time().to_msg()
        pt.header.frame_id = frame_id
        pt.point.x = X
        pt.point.y = Y
        pt.point.z = Z
        pt_map = self.tf_buffer.transform(pt, 'map', timeout=Duration(seconds=0.5))
        return pt_map.point.x, pt_map.point.y

    def _process(self, frame: np.ndarray, header):
        results = self.model(frame, conf=self.conf, verbose=False)

        events = []
        vis    = frame.copy()

        with self._lock:
            K            = self._K
            depth        = self._depth.copy() if self._depth is not None else None
            camera_frame = self._camera_frame

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                conf       = float(box.conf[0])
                cls_name   = self.model.names[int(box.cls[0])]
                event_type = EVENT_TYPE_MAP.get(cls_name)

                if event_type is None:
                    continue

                # 클래스별 confidence 임계값 적용
                if conf < CONF_MAP.get(cls_name, CONF_THRESH):
                    continue

                cu, cv_ = (x1 + x2) // 2, (y1 + y2) // 2

                # bbox 중심이 화면 상단 30% 이내면 스킵 — 천장/벽 오탐 방지
                if cv_ < frame.shape[0] * 0.3:
                    continue

                obj_x, obj_y = None, None
                if K is not None and depth is not None and camera_frame:
                    z = self._depth_at(depth, cu, cv_)
                    if 0.2 < z < 8.0:
                        fx, fy = K[0, 0], K[1, 1]
                        cx, cy = K[0, 2], K[1, 2]
                        X = (cu - cx) * z / fx
                        Y = (cv_ - cy) * z / fy
                        try:
                            obj_x, obj_y = self._to_map(X, Y, z, camera_frame)
                        except Exception as e:
                            self.get_logger().warn(
                                f'[{self.ns}] TF 변환 실패: {e}',
                                throttle_duration_sec=5.0)

                events.append({
                    'event_type': event_type,
                    'class':      cls_name,
                    'confidence': round(conf, 3),
                    'obj_x':      round(obj_x, 3) if obj_x is not None else None,
                    'obj_y':      round(obj_y, 3) if obj_y is not None else None,
                })

                col = EVENT_COLOR[event_type]
                cv2.rectangle(vis, (x1, y1), (x2, y2), col, 2)
                label = f'{cls_name} {conf:.2f}'
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(vis, (x1, y1 - th - 6), (x1 + tw + 4, y1), col, -1)
                cv2.putText(vis, label, (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        img_msg = self.bridge.cv2_to_imgmsg(vis, encoding='bgr8')
        img_msg.header = header
        self._pub_img.publish(img_msg)

        detected_types = {ev['event_type'] for ev in events}
        for et in list(self._confirm_counts):
            if et not in detected_types:
                self._confirm_counts[et] = 0

        confirmed = []
        now_ts = time.monotonic()
        for ev in events:
            et = ev['event_type']
            self._confirm_counts[et] = self._confirm_counts.get(et, 0) + 1
            if self._confirm_counts[et] < 2:
                continue

            active = self._active_events.get(et)
            if active is not None:
                ax, ay, at = active
                elapsed = now_ts - at
                if elapsed < 600.0:
                    x, y = ev['obj_x'], ev['obj_y']
                    if x is None or ax is None:
                        continue
                    if math.hypot(x - ax, y - ay) < 1.0:
                        continue

            confirmed.append(ev)
            self._active_events[et] = (ev['obj_x'], ev['obj_y'], now_ts)
            self._confirm_counts[et] = 0

        if not confirmed:
            return

        ts            = datetime.now(timezone.utc)
        robot_id      = ROBOT_ID_MAP.get(self.ns, self.ns.lstrip('/'))
        floor         = FLOOR_MAP.get(self.ns, 1)
        snapshot_name = f'img_{robot_id}_{ts.strftime("%Y%m%d_%H%M%S_%f")}.jpg'
        cv2.imwrite(str(SNAPSHOT_DIR / snapshot_name), vis)

        for ev in confirmed:
            payload = {
                'msg_id':       str(uuid.uuid4()),
                'version':      '2.0',
                'event_type':   ev['event_type'],
                'class':        ev['class'],
                'robot_id':     robot_id,
                'confidence':   ev['confidence'],
                'location':     {
                    'x':     ev['obj_x'],
                    'y':     ev['obj_y'],
                    'floor': floor,
                },
                'snapshot_ref': snapshot_name,
                'timestamp':    ts.isoformat(),
            }
            msg = String()
            msg.data = json.dumps(payload, ensure_ascii=False)
            self._pub_event.publish(msg)

        self.get_logger().info(f'[{self.ns}] IF-05 발행: {[ev["class"] for ev in confirmed]}')


def main(args=None):
    rclpy.init(args=args)
    node = DetectorNode()
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
