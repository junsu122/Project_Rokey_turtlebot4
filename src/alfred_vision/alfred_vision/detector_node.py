#!/usr/bin/env python3
import os
import json
import uuid
import threading
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/usr/lib/x86_64-linux-gnu/qt5/plugins'

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

DEFAULT_MODEL = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', 'share',
    'alfred_vision', 'resource', 'best.pt'
)
CONF_THRESH  = 0.4
SNAPSHOT_DIR = Path('/tmp/detection_snapshots')
DEPTH_PATCH  = 4

ROBOT_ID_MAP = {
    '/robot2': 'robot2',
    '/robot4': 'robot4',
}
FLOOR_MAP = {
    '/robot2': 1,
    '/robot4': 2,
}
EVENT_TYPE_MAP = {
    'fire':    'FIRE',
    'patient': 'INJURED_PERSON',
    'pistol':  'SUSPICIOUS_PERSON',
    'knife':   'SUSPICIOUS_PERSON',
    'wallet':  'LOST_ITEM',
    'bag':     'LOST_ITEM',
    'phone':   'LOST_ITEM',
}
EVENT_COLOR = {
    'FIRE':              (0,   60,  255),
    'INJURED_PERSON':    (0,   165, 255),
    'SUSPICIOUS_PERSON': (0,   255, 255),
    'LOST_ITEM':         (255, 200,   0),
}


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

        qos_be = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)

        self._lock            = threading.Lock()
        self._K               = None
        self._depth           = None
        self._camera_frame    = None
        self._latest_frame    = None
        self._first_frame     = True
        self._last_infer_time = 0.0

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
        import time
        now = time.monotonic()
        if now - self._last_infer_time < 3.0:
            return
        self._last_infer_time = now

        try:
            buf   = np.frombuffer(rgb_msg.data, dtype=np.uint8)
            frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
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
            self._process(frame, rgb_msg.header)
        except Exception as e:
            self.get_logger().error(f'[{self.ns}] 동기화 콜백 오류: {e}')

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

                cu, cv_ = (x1 + x2) // 2, (y1 + y2) // 2

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

        with self._lock:
            self._latest_frame = vis

        if not events:
            return

        ts            = datetime.now(timezone.utc)
        robot_id      = ROBOT_ID_MAP.get(self.ns, self.ns.lstrip('/'))
        floor         = FLOOR_MAP.get(self.ns, 1)
        snapshot_name = f'img_{robot_id}_{ts.strftime("%Y%m%d_%H%M%S_%f")}.jpg'
        cv2.imwrite(str(SNAPSHOT_DIR / snapshot_name), vis)

        for ev in events:
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

        self.get_logger().info(f'[{self.ns}] IF-05 발행: {[ev["class"] for ev in events]}')


def main(args=None):
    rclpy.init(args=args)
    node = DetectorNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    win_name    = f'detection [{node.ns}]'
    win_opened  = False
    try:
        while rclpy.ok():
            with node._lock:
                frame = node._latest_frame
            if frame is not None:
                cv2.imshow(win_name, frame)
                if not win_opened:
                    win_opened = True
                    node.get_logger().info(f'[{node.ns}] cv2 창 열림')
            cv2.waitKey(30)
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
