#!/usr/bin/env python3
"""웹캠 기반 ArUco 추적 노드. 사용자 ID와 거리 추정 테스트에 사용한다."""

import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


def numpy_to_imgmsg(frame: np.ndarray, frame_id: str, stamp) -> Image:
    #OpenCV 이미지 배열을 ROS Image 메시지로 변환한다.
    msg = Image()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id
    msg.height, msg.width = frame.shape[:2]
    msg.encoding = 'bgr8'
    msg.step = frame.shape[1] * 3
    msg.data = frame.tobytes()
    return msg


def parse_int_list(value: object) -> List[int]:
    #리스트나 스트링 형식으로 들어 올 수 있기 때문에 고정적으로 list형식으로 반환한다
    if isinstance(value, str):
        return [int(item.strip()) for item in value.split(',') if item.strip()]
    return [int(item) for item in value]


def make_camera_matrix(
    width: int,
    height: int,
    horizontal_fov_deg: float,
    camera_matrix_param: Sequence[float],
) -> np.ndarray:
    """카메라 내부 파라미터 행렬(camera matrix)을 만든다.
    """
    if len(camera_matrix_param) == 9:
        return np.array(camera_matrix_param, dtype=np.float64).reshape(3, 3)

    hfov = math.radians(horizontal_fov_deg)
    fx = width / (2.0 * math.tan(hfov / 2.0))
    fy = fx
    cx = width / 2.0
    cy = height / 2.0
    return np.array([
        [fx, 0.0, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)


def make_dist_coeffs(dist_coeffs_param: Sequence[float]) -> np.ndarray:
    """카메라 왜곡 계수를 만든다.

    일반적인 OpenCV 왜곡 계수 길이(4, 5, 8, 12, 14)로 들어오면 그대로 사용하고,
    없거나 형식이 맞지 않으면 왜곡이 없다고 보고 0 배열을 사용한다.
    """
    if len(dist_coeffs_param) in (4, 5, 8, 12, 14):
        return np.array(dist_coeffs_param, dtype=np.float64)
    return np.zeros((5,), dtype=np.float64)


def estimate_pose_single_markers(corners, marker_size, camera_matrix, dist_coeffs):
    """cv2.aruco.estimatePoseSingleMarkers 대체 (신버전 OpenCV에서 제거됨).

    동일 방식: 마커 4코너 + 실제 크기로 PnP(solvePnP) → rvec/tvec.
    반환 shape도 기존 API와 동일: rvecs (N,1,3), tvecs (N,1,3).
    """
    half = marker_size / 2.0
    obj_points = np.array([
        [-half,  half, 0.0],
        [ half,  half, 0.0],
        [ half, -half, 0.0],
        [-half, -half, 0.0],
    ], dtype=np.float32)

    rvecs, tvecs = [], []
    for corner in corners:
        _, rvec, tvec = cv2.solvePnP(
            obj_points, corner[0], camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE)
        rvecs.append(rvec.reshape(1, 3))
        tvecs.append(tvec.reshape(1, 3))
    return np.array(rvecs), np.array(tvecs), None


class ArucoTrackerNode(Node):
    """카메라 프레임에서 ArUco 마커를 검출하고 사용자 마커 정보를 발행하는 노드.

    출력 토픽:
    - `/aruco_tracker/markers`: 검출된 전체 마커 목록(JSON 문자열)
    - `/aruco_tracker/user`: 현재 사용자로 선택된 마커 정보(JSON 문자열)
    - `/aruco_tracker/image_debug`: 마커와 축이 그려진 디버그 이미지
    """

    def __init__(self):
        """파라미터, 카메라, ArUco detector, ROS publisher/timer를 초기화한다."""
        super().__init__('aruco_tracker_node')

        self.declare_parameter('camera_index', 0)
        self.declare_parameter('image_width', 640)
        self.declare_parameter('image_height', 480)
        self.declare_parameter('framerate', 30.0)
        self.declare_parameter('frame_id', 'aruco_cam_frame')
        self.declare_parameter('marker_size_m', 0.165)
        self.declare_parameter('marker_ids', [0, 1])
        self.declare_parameter('user_marker_id', -1)
        self.declare_parameter('dictionary', 'DICT_4X4_1000')
        self.declare_parameter('horizontal_fov_deg', 35.0)
        self.declare_parameter('camera_matrix', [])
        self.declare_parameter('dist_coeffs', [])
        self.declare_parameter('show_window', False)
        self.declare_parameter('publish_debug_image', True)

        self._camera_index = int(self.get_parameter('camera_index').value)
        self._width = int(self.get_parameter('image_width').value)
        self._height = int(self.get_parameter('image_height').value)
        self._fps = float(self.get_parameter('framerate').value)
        self._frame_id = str(self.get_parameter('frame_id').value)
        self._marker_size_m = float(self.get_parameter('marker_size_m').value)
        self._valid_marker_ids = set(parse_int_list(self.get_parameter('marker_ids').value))
        self._selected_user_id = int(self.get_parameter('user_marker_id').value)
        self._show_window = bool(self.get_parameter('show_window').value)
        self._publish_debug_image = bool(self.get_parameter('publish_debug_image').value)

        dictionary_name = str(self.get_parameter('dictionary').value)
        self._aruco_dict = self._make_dictionary(dictionary_name)
        self._detector_params = cv2.aruco.DetectorParameters()
        self._detector = self._make_detector()

        camera_matrix_param = self.get_parameter('camera_matrix').value
        dist_coeffs_param = self.get_parameter('dist_coeffs').value
        horizontal_fov_deg = float(self.get_parameter('horizontal_fov_deg').value)
        self._camera_matrix = make_camera_matrix(
            self._width, self._height, horizontal_fov_deg, camera_matrix_param)
        self._dist_coeffs = make_dist_coeffs(dist_coeffs_param)

        self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_V4L2)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        if not self._cap.isOpened():
            raise RuntimeError(f'Cannot open camera index: {self._camera_index}')

        actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        self._marker_pub = self.create_publisher(String, '/aruco_tracker/markers', 10)
        self._user_pub = self.create_publisher(String, '/aruco_tracker/user', 10)
        self._image_pub = self.create_publisher(Image, '/aruco_tracker/image_debug', 10)
        self.create_timer(1.0 / self._fps, self._process_frame)

        if len(camera_matrix_param) != 9:
            self.get_logger().warn(
                'camera_matrix is not set. Using approximate FOV calibration; '
                'distance is good for rough testing only.'
            )
        self.get_logger().info(
            f'ArUco tracker ready: camera={self._camera_index}, '
            f'{actual_width}x{actual_height}@{actual_fps:.0f}fps, '
            f'dictionary={dictionary_name}, marker_size={self._marker_size_m:.3f}m, '
            f'ids={sorted(self._valid_marker_ids)}'
        )

    def _make_dictionary(self, dictionary_name: str):
        """OpenCV에 등록된 ArUco dictionary 객체를 만든다."""
        if not hasattr(cv2.aruco, dictionary_name):
            raise RuntimeError(f'Unknown ArUco dictionary: {dictionary_name}')
        return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))

    def _make_detector(self):
        """OpenCV 버전에 맞는 ArUco detector를 만든다.

        최신 OpenCV에는 `cv2.aruco.ArucoDetector` 클래스가 있고, 구버전은
        `cv2.aruco.detectMarkers()` 함수를 직접 호출해야 한다. 두 버전을 모두
        지원하기 위해 detector 객체가 있으면 사용하고, 없으면 None을 반환한다.
        """
        if hasattr(cv2.aruco, 'ArucoDetector'):
            return cv2.aruco.ArucoDetector(self._aruco_dict, self._detector_params)
        return None

    def _detect_markers(self, gray: np.ndarray):
        """grayscale 이미지에서 ArUco 마커를 검출한다."""
        if self._detector is not None:
            return self._detector.detectMarkers(gray)
        return cv2.aruco.detectMarkers(
            gray, self._aruco_dict, parameters=self._detector_params)

    def _process_frame(self):
        """카메라 frame 하나를 읽고 마커 검출/거리 계산/결과 발행을 수행한다.

        timer callback으로 주기적으로 실행된다. 처리 순서는 다음과 같다.
        1. 카메라 frame 읽기
        2. ArUco 마커 검출
        3. 허용된 marker id만 필터링
        4. pose와 거리, bbox 크기 계산
        5. 사용자 마커 선택
        6. JSON 결과와 debug image 발행
        """
        ok, frame = self._cap.read()
        stamp = self.get_clock().now().to_msg()
        if not ok:
            self.get_logger().warn('Failed to capture frame', throttle_duration_sec=2.0)
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detect_markers(gray)
        markers = []

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            rvecs, tvecs, _ = estimate_pose_single_markers(
                corners,
                self._marker_size_m,
                self._camera_matrix,
                self._dist_coeffs,
            )

            for index, marker_id_raw in enumerate(ids.flatten()):
                marker_id = int(marker_id_raw)
                if marker_id not in self._valid_marker_ids:
                    continue

                rvec = rvecs[index][0]
                tvec = tvecs[index][0]
                distance_m = float(np.linalg.norm(tvec))
                x_m, y_m, z_m = (float(tvec[0]), float(tvec[1]), float(tvec[2]))
                center = corners[index][0].mean(axis=0)
                center_x, center_y = float(center[0]), float(center[1])
                _bx, _by, bbox_w, bbox_h = cv2.boundingRect(
                    corners[index][0].astype(np.float32))
                img_h, img_w = frame.shape[:2]

                # marker_speed_governor가 속도 계산에 쓸 수 있도록 거리와 bbox 정보를 함께 저장한다.
                markers.append({
                    'id': marker_id,
                    'distance_m': distance_m,
                    'x_m': x_m,
                    'y_m': y_m,
                    'z_m': z_m,
                    'center_x': center_x,
                    'center_y': center_y,
                    'bbox_width_px': float(bbox_w),
                    'bbox_height_px': float(bbox_h),
                    'image_width': float(img_w),
                    'image_height': float(img_h),
                })

                cv2.drawFrameAxes(
                    frame,
                    self._camera_matrix,
                    self._dist_coeffs,
                    rvec,
                    tvec,
                    self._marker_size_m * 0.5,
                )
                label = f'ID {marker_id}  {distance_m:.2f}m'
                cv2.putText(
                    frame,
                    label,
                    (int(center_x) - 70, max(int(center_y) - 20, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )

        selected_user = self._select_user(markers)
        self._publish_results(markers, selected_user, stamp)

        if selected_user is not None:
            text = f"USER {selected_user['id']}  {selected_user['distance_m']:.2f}m"
            color = (0, 255, 0)
        else:
            text = 'USER marker not found'
            color = (0, 0, 255)
        cv2.putText(frame, text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        if self._publish_debug_image:
            self._image_pub.publish(numpy_to_imgmsg(frame, self._frame_id, stamp))
        if self._show_window:
            cv2.imshow('aruco_tracker', frame)
            cv2.waitKey(1)

    def _select_user(self, markers: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """검출된 마커들 중 현재 사용자 마커를 하나 선택한다.

        - `user_marker_id` 파라미터가 0 이상이면 해당 id만 사용자로 인정한다.
        - 지정되어 있지 않으면 가장 가까운 마커를 사용자로 자동 선택하고,
          이후 frame에서도 같은 id를 계속 추적한다.
        """
        if not markers:
            return None

        if self._selected_user_id >= 0:
            for marker in markers:
                if marker['id'] == self._selected_user_id:
                    return marker
            return None

        nearest_marker = min(markers, key=lambda marker: marker['distance_m'])
        self._selected_user_id = int(nearest_marker['id'])
        self.get_logger().info(f'Assigned user marker id: {self._selected_user_id}')
        return nearest_marker

    def _publish_results(self, markers, selected_user, stamp):
        """전체 마커 목록과 선택된 사용자 마커 정보를 JSON 문자열로 발행한다.

        `/aruco_tracker/user`는 marker_speed_governor가 직접 구독하는 핵심 토픽이다.
        여기에는 사용자 마커가 보이는지(`found`), 사용자 id, 거리, bbox 크기가 들어간다.
        """
        payload = {
            'stamp': {
                'sec': int(stamp.sec),
                'nanosec': int(stamp.nanosec),
            },
            'markers': markers,
        }
        self._marker_pub.publish(String(data=json.dumps(payload)))

        user_payload = {
            'stamp': payload['stamp'],
            'found': selected_user is not None,
            'user_id': self._selected_user_id if self._selected_user_id >= 0 else None,
            'user': selected_user,
        }
        self._user_pub.publish(String(data=json.dumps(user_payload)))

        if selected_user is not None:
            self.get_logger().info(
                f"USER id={selected_user['id']} "
                f"distance={selected_user['distance_m']:.2f}m "
                f"z={selected_user['z_m']:.2f}m",
                throttle_duration_sec=1.0,
            )

    def destroy_node(self):
        """노드 종료 시 카메라와 OpenCV 창 자원을 정리한다."""
        if hasattr(self, '_cap'):
            self._cap.release()
        if self._show_window:
            cv2.destroyAllWindows()
        super().destroy_node()


def main():
    """aruco_tracker_node 실행 진입점."""
    rclpy.init()
    node = None
    try:
        node = ArucoTrackerNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
