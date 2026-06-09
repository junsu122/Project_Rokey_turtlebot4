# ROS2 → Web 실시간 브릿지 연결 요청

## 배경
ROS2(Linux, Ubuntu/Humble)에서 발행하는 토픽 데이터를 **웹 클라이언트(Windows)** 가 실시간으로 받을 수 있는지 테스트하고 있습니다. 중계는 `rosbridge_suite`(websocket 기반, JSON 프로토콜)를 사용합니다.

```
[ROS2 노드] → (ROS topic) → [rosbridge_websocket] → (websocket, JSON) → [web client = 여기]
```

## Linux 쪽에서 이미 확인된 것 (정상 동작)

아래 3개 터미널을 띄워서 ROS2 토픽 발행 → rosbridge 중계 → websocket 수신까지 **로컬에서는 정상 동작을 확인**했습니다.

**터미널 1 — 토픽 발행 노드**
```bash
cd ~/test_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run alfred_driving behavior_node
```
→ `/robot2/robot_state` 토픽으로 1초마다 상태 메시지 발행 (`alfred_interfaces/msg/RobotState`)

**터미널 2 — rosbridge websocket 서버**
```bash
cd ~/test_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```
→ `ws://0.0.0.0:9090` 에서 websocket 서버 구동 (외부 접속 허용 상태로 listen 중)

**터미널 3 — websocket 클라이언트 (파이썬 테스트)**
```python
import json, websocket
ws = websocket.create_connection("ws://localhost:9090")
ws.send(json.dumps({"op": "subscribe", "topic": "/robot2/robot_state", "type": "alfred_interfaces/msg/RobotState"}))
print("subscribed. waiting...")
while True:
    print(ws.recv())
```
→ 1초마다 아래와 같은 JSON이 수신됨:
```json
{"op": "publish", "topic": "/robot2/robot_state", "msg": {"robot_id": "robot2", "state": "IDLE", "pose": {...}, "battery": 100, ...}}
```

## 네트워크 정보

- **rosbridge 서버(Linux) IP**: `192.168.107.81`, 포트 `9090`
- **연결할 클라이언트(Windows) IP**: `192.168.107.84`
- 같은 사설 네트워크 대역(`192.168.107.x`)이라 라우팅 문제는 없을 것으로 보임
- 서버는 `0.0.0.0:9090`으로 바인딩되어 있어 외부 접속 자체는 가능한 상태

## Windows 쪽에 부탁하고 싶은 것

Windows에서 아래에 websocket으로 접속해서 동일한 `subscribe` 메시지를 보내고, 들어오는 JSON을 출력/표시하는 클라이언트를 만들고 싶습니다.

```
ws://192.168.107.81:9090
```

**구독 요청 형식 (rosbridge v2 프로토콜)**:
```json
{"op": "subscribe", "topic": "/robot2/robot_state", "type": "alfred_interfaces/msg/RobotState"}
```

**수신 메시지 형식**:
```json
{"op": "publish", "topic": "/robot2/robot_state", "msg": { ... }}
```

### 확인하고 싶은 것
1. Windows에서 브라우저 JS / Node.js / Python 중 어떤 방식으로 websocket 클라이언트를 만드는 게 가장 간단한지
2. `192.168.107.81:9090`으로 연결 시도했을 때 연결이 되는지 (안 되면 Windows 방화벽/네트워크 설정 확인 필요)
3. 받은 JSON 메시지를 화면에 표시하는 최소 예제 코드

### 참고: 다른 토픽도 같은 방식으로 구독 가능
- `/detection` — `std_msgs/Bool` (예: 물체 감지 여부)
- 그 외 ROS2 그래프에 떠있는 임의의 토픽 — `ros2 topic list -t`로 확인 가능

## 메시지 타입 정의 참고 (alfred_interfaces/msg/RobotState)
```
string robot_id
string state              # IDLE|PATROL|INTERACTING|RESERVED|HANDOVER_READY|ESCORTING|WAITING_HANDOVER|RETURNING|EMERGENCY|ERROR
geometry_msgs/Pose2D pose # x, y, theta
int32 battery             # 0~100 (%)
string current_task_id
string task_status        # ACCEPTED|RUNNING|SUCCEEDED|FAILED|""
string error_code
string timestamp          # ISO 8601, ms 포함
```
