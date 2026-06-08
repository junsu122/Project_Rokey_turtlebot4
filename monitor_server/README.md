# Monitoring Server

This directory contains the monitoring-only server.

It receives ROS2 messages, stores observation data in SQLite, and serves
the administrator dashboard. It does not create missions, dispatch tasks, or
control robots.

## Runtime Flow

```text
Robot status   -> ROS2 /robot2/robot_state, /robot4/robot_state -> monitor_server -> latest_robot_status + robot_status_log
Detector event -> ROS2 /robot2/vision/alert, /robot4/vision/alert -> monitor_server -> events
Admin browser -> Flask API/dashboard -> read SQLite
```

## Run

```bash
cd /home/rokey/Desktop/alfred_ws/monitor_server
source /opt/ros/humble/setup.bash
source ../install/setup.bash
unset ROS_DISCOVERY_SERVER
export ROS_DOMAIN_ID=2
python3 main.py
```

Dashboard:

```text
http://localhost:5000
admin / admin1234
```

## Kept Modules

| File | Role |
| --- | --- |
| `main.py` | Starts ROS2 subscriptions and Flask API |
| `ros_ingest.py` | ROS2 RobotState/Event subscriptions |
| `robot_registry.py` | Robot status ingestion into SQLite |
| `event_service.py` | Detector event ingestion |
| `db.py` | SQLite tables for monitoring records |
| `api.py` | Read-only dashboard/API routes plus event resolve |
| `web/dashboard.html` | Admin monitoring dashboard |

## ROS2 Topics

The server subscribes only to:

```text
/robot2/robot_state
/robot4/robot_state
/robot2/vision/alert
/robot4/vision/alert
```

## SQLite Tables

```text
latest_robot_status
robot_status_log
events
ui_usage_log
monitor_counters
```

Old mission/task tables may still exist inside an existing `fms.db` file if the
database was created before the monitoring-only refactor, but this server no
longer creates, writes, or reads them.

## Test Tools

```bash
ros2 topic echo /robot2/robot_state
ros2 topic echo /robot2/vision/alert
```

## WebRTC 영상 수신 (⚠ 작업 중 · 미완성)

대시보드 **영상 탭**에서 로봇 카메라 라이브 영상을 본다. 미디어는 **로봇 ↔ 브라우저 P2P**
(모니터 서버 우회), 서버는 시그널링 URL 메타데이터(`web/video_sources.json`)만 제공한다.

### 구성
- **브라우저(수신)**: `web/dashboard.html` 영상 탭 — `/api/video_sources` 폴링 → 로봇별 카드 →
  `연결` 클릭 시 `RTCPeerConnection`(recvonly) offer 생성 → `signal_url`로 POST → answer 수신.
  같은 LAN 가정이라 STUN/TURN 미사용(`iceServers:[]`).
- **로봇(송신)**: `src/alfred_vision/alfred_vision/video_sender_node.py` — `CompressedImage` 구독,
  `0.0.0.0:8081` 에서 `POST /offer` 시그널링.
- **소스 설정**: `web/video_sources.json` — 현재 robot2=`192.168.107.102`, robot4=`192.168.107.104`.

### 로봇 측 실행 (각 로봇 PC)
```bash
pip install aiortc aiohttp opencv-python numpy        # 최초 1회
source /opt/ros/humble/setup.bash && source ~/alfred_ws/install/setup.bash
ros2 run alfred_vision video_sender_node \
  --ros-args -p image_topic:=/camera/image_raw/compressed   # 실제 카메라 토픽으로
```
연결 확인(관제 PC): `curl -X POST http://192.168.107.102:8081/offer -d '{"sdp":"x","type":"offer"}' -H "Content-Type: application/json"`

### ⚠ 남은 작업 (TODO)
- [ ] 로봇에서 `video_sender_node` 실제 구동/검증 — 현재 8081 포트 미응답(노드 미실행)으로
      **end-to-end 연결 미확인**. UI·시그널링 URL·버튼 활성화까지만 검증됨.
- [ ] `image_topic` 확정 — 기본값 `/camera/image_raw/compressed`. OAK-D 실제 압축 토픽명으로 맞춰야 함
      (압축 토픽 없으면 `image_transport republish` 필요).
- [ ] 로봇 방화벽 8081 허용(`sudo ufw allow 8081`) 확인.
- [ ] 자동 재연결/연결 상태 모니터링, 다중 시청자 등은 미구현.
