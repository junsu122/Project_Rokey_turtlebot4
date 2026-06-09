# 노트북(연산 PC) rosbridge 연결 매뉴얼

> ALFRED 키오스크(UI) → **이 노트북** 으로 고객 요청 JSON(`/information`)을 받기 위한 설정.
> 이 노트북 = TurtleBot4(robot2) 와 연결되어 **Nav2/localization** 을 돌리는 우분투 PC.

## 0. 구성 한눈에

| 기기 | IP | 역할 |
|------|------|------|
| 키오스크(UI) | 192.168.107.84 (Windows) | `/information` 을 **보냄** (rosbridge 클라이언트) |
| **이 노트북** | **192.168.107.41** (Ubuntu) | rosbridge 서버 실행 + `/information` **받음** + Nav2 |
| 로봇 | robot2 / 192.168.107.102 | bringup (도메인 2) |

키오스크가 `ws://192.168.107.41:9090` 으로 붙습니다. → **이 노트북에서 rosbridge 서버가 떠 있어야** 합니다.

> **IP가 바뀌면**: 키오스크 `.env` 의 `VITE_ROSBRIDGE_HOST` 한 줄(IP만)을 새 값으로 바꾸고 UI 재시작. 그 한 곳만 고치면 전체 반영됩니다.

---

## 1. 사전 조건
- 키오스크와 **같은 WiFi**(turtle07, 192.168.107.x).
- **Nav2 를 띄우는 그 터미널**(ROS 2 Humble 환경이 소싱되고, `ros2 topic list` 에 `/robot2/...` 가 보이는 상태)에서 작업.

## 2. 설치 (최초 1회만)
```bash
# 이미 설치돼 있는지 확인
ros2 pkg prefix rosbridge_server
#  → 경로가 나오면 설치 끝. 3번으로.
#  → "Package not found" 면 아래 설치:

sudo apt update && sudo apt install -y ros-humble-rosbridge-suite
```
설치 중 `EXPKEYSIG ... Open Robotics`(GPG 키 만료) 에러가 나면, 키부터 갱신 후 위 명령 재실행:
```bash
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
```

## 3. 실행 (시연할 때마다)
```bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```
- `Rosbridge WebSocket server started on port 9090` 가 보이면 정상.
- **이 터미널은 켜둡니다.** (끄면 연결 끊김)

## 4. 수신 확인
키오스크 patrol 화면을 **터치**(→ `INTERACTING`)하거나 **목적지를 선택**(→ `ESCORT`)한 뒤,
이 노트북의 **다른 터미널**에서:
```bash
ros2 topic list | grep information      # /information 이 보이면 연결됨
ros2 topic echo /information            # 키오스크가 보낸 메시지가 찍히면 성공
```
토픽 타입은 **`std_msgs/msg/String`**, 내용은 `data` 안에 IF-01 JSON 문자열입니다:
```yaml
data: '{"msg_id":"msg_1_...","version":"2.0","request_id":"REQ_2_...","robot_id":"robot2","request_type":"INTERACTING","origin":{...},"customer":{...},"timestamp":"..."}'
---
```
받는 노드(Driving 트랙)에서는 `json.loads(msg.data)` 로 파싱해 쓰면 됩니다.

## 5. 참고
- **방화벽**: 연결이 안 되면 9090 열기 — `sudo ufw allow 9090/tcp` (ufw 사용 시).
- **메시지 타입**: 기본은 **`std_msgs/String`** — 임의 JSON 을 ROS 로 보내는 표준 방식이라 **커스텀 .msg 가 필요 없습니다**(키오스크가 `data` 에 JSON 문자열을 담아 advertise·publish). 나중에 전용 메시지(예: `alfred_msgs/Information`) 를 정의하면, 키오스크 `.env` 의 `VITE_ROS_INFO_MSG_TYPE` 를 그 타입으로 바꾸면 구조화 필드를 그대로 보냅니다(코드 수정 없이).
- **종료**: 실행 터미널에서 `Ctrl + C`.

---
문제 생기면 키오스크 담당에게 이 노트북의 `ros2 launch ...` 로그와 `ros2 topic list` 결과를 전달하세요.
