# 다중 로봇 릴레이 에스코트 — Alfred 워크스페이스

> ROKEY 7기 지능1 Team Alfred · 교통허브 내 다중 AMR(TurtleBot4 2대) 릴레이 에스코트 시스템
> 본 저장소는 **하나의 ROS2 워크스페이스(모노레포)** 다. 로봇 유닛의 **ROS2 패키지 전체**(`src/`),
> 중앙 관제 **FMS 서버**(`fms_server/` · 순수 Python·비‑ROS), 통합 계약·다이어그램(`docs/`)을 함께 담는다.
> 프로토콜 **v2.1** · 유닛↔FMS 전송 **MQTT JSON** · 한 줄 요약: *"로봇은 보고하고, FMS는 task를 내린다."*

---

## 구성 — 두 트랙이 한 저장소에

| 트랙 | 위치 | 성격 | 빌드/실행 |
|---|---|---|---|
| **로봇 유닛 (ROS2)** | `src/` (6개 패키지) | ROS2 Humble · colcon | `colcon build` → `ros2 launch` |
| **FMS 서버** | `fms_server/` | 순수 Python · **ROS 비의존** | `python3 main.py` |

> ⚠️ **FMS는 ROS를 모른다.** 로봇 유닛 내부는 ROS2지만, 유닛↔FMS는 **MQTT JSON(IF‑01~05)** 한 채널뿐이고, 그 변환은 각 유닛의 **브리지 노드**(`alfred_bridge`)가 전담한다. 그래서 `fms_server/`는 `src/` 밖에 둔다(colcon 비대상).

처음 온 팀원은 → 자기 트랙: **로봇이면 [§2 ROS2 워크스페이스](#2-ros2-워크스페이스-src), FMS면 [§5 FMS 서버](#5-fms-서버-fms_server)**. 통합 계약은 누구나 **[`docs/INTERFACE_CONTRACT.md`](docs/INTERFACE_CONTRACT.md)** 필독.

---

## 0. 시스템 개요

교통허브에서 **TurtleBot4 2대(robot2=1층, robot4=2층)** 가 고객을 **릴레이로 에스코트**한다. 평소 각 로봇은 정해진 경로를 **순찰**하며 요청을 기다리고, 요청을 받으면 목적지까지 안내하며, 순찰 중 이상 상황을 감지하면 대응한다.

### 로봇의 동작 (크게 3가지)
- **순찰 (기본 상태)** — task가 없으면 스스로 경로를 돌며 "도움이 필요하면 불러주세요" 안내(화면 터치 / "헬로 알프레드")
- **에스코트** — 고객 요청 수신 → 목적지 안내. 층이 다르면 1층 로봇이 핸드오버 지점까지, 2층 로봇이 이어받아 최종 목적지까지(**릴레이**). 고객 프로필(일반/시각장애 등)에 따라 주행 방식 분기
- **이벤트 대응** — 순찰 중 FIRE / SUSPICIOUS_PERSON / 유실물 감지 시 규정 동작

### FMS의 역할 (중앙 조율)
로봇은 주행을 스스로 하고, **FMS는 "무엇을 하라(task)"만 조율**한다: 미션 생성·로봇 배정·task(IF‑03) 발행·상태(IF‑02) 관측·핸드오버 승인 및 지연(3초) 측정·이상(IF‑05) 기록·관제 UI. Mission State는 **FMS만 소유**하고, 로봇 바퀴를 직접 제어하지 않는다.

### 서비스 흐름 (정상 시나리오)
```
고객이 1층 robot2 호출 → robot2가 핸드오버 지점까지 안내
→ 2층 robot4가 이어받아(핸드오버) 최종 목적지까지 안내
(같은 층이면 robot2가 직행)
```

---

## 1. 시스템 아키텍처 (트랙 분업)

4개 트랙이 **정의된 인터페이스(IF‑01~05)** 로만 통신한다.

| 트랙 | 패키지/위치 | 역할 | FMS로 보냄 | FMS에서 받음 |
|---|---|---|---|---|
| **Interaction** | `alfred_interaction` | 고객 응대·목적지 확정(STT/LLM/TTS/UI) | IF‑01 (요청) | — |
| **Driving/Escort** | `alfred_driving` | 자율주행·핸드오버 수행 | IF‑02 (상태), task_ack | **IF‑03 (task) — 유일 입력** |
| **Vision** | `alfred_vision` | 카메라 YOLO 이상감지 | IF‑05 (이벤트) | — |
| **Bridge** | `alfred_bridge` | ROS↔MQTT/IF 양방향 번역(유닛당 1개) | (중계) | (중계) |
| **FMS** | `fms_server` | 미션·상태·핸드오버 조율 | IF‑03 | IF‑01/02/05 |
| **관제 UI** | `fms_server/web` | 모니터링 | — | Flask REST(GET) |

자세한 그림:
- [`docs/SYSTEM_ARCHITECTURE.png`](docs/SYSTEM_ARCHITECTURE.png) — 제어 평면(MQTT/HTTP) + 데이터 평면(영상)
- [`docs/DEPLOYMENT_TOPOLOGY.png`](docs/DEPLOYMENT_TOPOLOGY.png) / [`..._SEPARATED.png`](docs/DEPLOYMENT_TOPOLOGY_SEPARATED.png) — 어느 PC에 무엇이 도나
- [`docs/ROBOT_UNIT_NODES.png`](docs/ROBOT_UNIT_NODES.png) — 로봇 유닛 내부 ROS2 노드 구성

---

## 2. ROS2 워크스페이스 (`src/`)

**배포판 ROS2 Humble.** 로봇 유닛 1대를 패키지 6벌로 구성한다. 로봇 2대(robot2/robot4)는 **패키지를 복제하지 않고** `robot_id` 파라미터로 두 번 launch 한다.

| 패키지 | 빌드 타입 | 내용 |
|---|---|---|
| `alfred_interfaces` | ament_cmake | IF‑01~05 커스텀 msg: `Request` `RobotState` `Task` `Event` `TaskAck` (`geometry_msgs/Pose2D` 사용) |
| `alfred_bridge` ⭐ | ament_python | `fms_bridge_node` — ROS↔MQTT/IF 변환, FMS와 **유일한 통신 창구**(paho‑mqtt) |
| `alfred_interaction` | ament_python | `ui_node` `stt_node` `llm_node` `tts_node` |
| `alfred_driving` | ament_python | `behavior_node`(Robot State 단독 소유) + nav2/localization 설정 자리 |
| `alfred_vision` | ament_python | `yolo_monitor_node` `video_sender_node` |
| `alfred_bringup` | ament_python | `unit.launch.py` + 로봇별 params(`robot2.yaml`/`robot4.yaml`) + maps |

> 현재 노드 본문은 **스켈레톤(스텁)** 이다. `colcon build`는 통과하며, 각 트랙이 `# TODO` 부분을 채운다.

### 트랙별 노드 책임
- **Interaction** (`alfred_interaction`): `stt_node`(음성→텍스트) → `llm_node`(목적지 정규화) → `tts_node`(발화), `ui_node`(터치·요청 조립). 목적지 확정 시 IF‑01 요청 생성.
- **Driving** (`alfred_driving`): `behavior_node`가 **Robot State 단독 소유** + nav2 goal 중재. 순찰·에스코트·이벤트대응은 **노드 분할이 아니라 한 노드 안의 동작 모듈**(상황은 상태이지 프로세스가 아님).
- **Vision** (`alfred_vision`): `yolo_monitor_node`(이상감지→IF‑05), `video_sender_node`(영상 데이터평면, FMS 우회·선택).
- **Bridge** (`alfred_bridge`): 유닛의 유일한 MQTT 창구. ROS↔IF 변환·멱등·거절 규칙을 한 곳에 집중.

### 로봇 상태 흐름 (behavior_node FSM)
```
PATROL ─(고객 호출)→ INTERACTING ─(IF-03 ESCORT 수락)→ ESCORTING
       → … → WAITING_HANDOVER → (RETURN_TO_BASE) → RETURNING → PATROL
```
- ⚠️ 호출 시 **PATROL→INTERACTING 전이 필수.** PATROL/IDLE에서 받은 ESCORT task는 거절되므로(§2 거절 규칙), 안 바꾸면 자기 escort를 거절한다.
- 두 번째 로봇(robot4)은 PATROL에서 `MOVE_TO_STANDBY`(ESCORT 계열 아님 → 수락)로 핸드오버 지점에 가 `HANDOVER_READY`가 된 뒤 `ESCORT_TO_FINAL`을 이어받는다.
- 일반 안내 / 시각장애 안내(ArUco 위치유지)는 `customer_profile`로 고르는 **EscortBehavior 내부 전략**. 사용자 ArUco 추적 등 "베이스를 제어하지 않는 감지"만 별도 노드로 분리 가능.

### 빌드 & 실행

```bash
# 사전: ROS2 Humble 설치 + paho-mqtt
sudo apt install ros-humble-desktop python3-colcon-common-extensions
pip install paho-mqtt

# 워크스페이스 루트(alfred_ws)에서
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash

# 로봇 유닛 기동 (유닛당 한 명령)
ros2 launch alfred_bringup unit.launch.py robot_id:=robot2   # 1층 유닛
ros2 launch alfred_bringup unit.launch.py robot_id:=robot4   # 2층 유닛
```

### 로봇 트랙 작업 시 필수 규칙
- **client_id 유일**: 브리지마다 다른 MQTT client_id(`bridge_robot2`, `bridge_robot4`). FMS는 `fms_server`.
- **멱등**: QoS 1은 중복 배달 가능 → 이미 처리한 `task_id` 재수신 시 무시.
- **거절 규칙(계약 §6.2)**: **PATROL/IDLE**(임무 없이 대기) 상태에서 받은 ESCORT 계열 task는 **REJECT**(유령 에스코트 방지). 임무 중 상태(INTERACTING·RESERVED·HANDOVER_READY·WAITING_HANDOVER·ESCORTING)는 수락.
- **브리지 매핑**: 각 트랙은 [`docs/bridge_config.template.yaml`](docs/bridge_config.template.yaml)의 `ros_topic`/`ros_type`를 자기 토픽으로 채운다.
- **시간 동기화(NTP)**: 핸드오버 "3초" 측정은 로봇 PC↔FMS PC timestamp 차이로 계산 → **전 기기 chrony(NTP) 동기화 필수.**

---

## 3. 인터페이스 요약 (상세는 계약 문서)

전송: **Mosquitto MQTT broker**, FMS 호스트 PC의 `:1883`. 페이로드 UTF‑8 JSON. `{id} ∈ {robot2, robot4}`.

| IF | 토픽 | 방향 | QoS | 용도 |
|---|---|---|---|---|
| IF‑01 | `robot/{id}/request` | 로봇→FMS | 1 | 미션 요청(ESCORT/CANCEL) |
| IF‑02 | `robot/{id}/status` | 로봇→FMS | 0 | 로봇 상태 + task 결과 보고 |
| IF‑03 | `robot/{id}/task` | FMS→로봇 | 1 | **task 발행(로봇 유일 입력)** |
| ACK | `robot/{id}/task_ack` | 로봇→FMS | 1 | task 수락/거절 |
| IF‑05 | `robot/{id}/event` | 로봇→FMS | 1 | 이상감지(FIRE/SUSPICIOUS_PERSON) |

**공통 필드**(모든 메시지): `msg_id`(uuid), `version`("2.1"), `timestamp`(ISO8601, ms 포함).

**task_type (4종)**: `MOVE_TO_STANDBY` · `ESCORT_TO_HANDOVER` · `ESCORT_TO_FINAL` · `RETURN_TO_BASE`
(순찰 task 없음 — 순찰은 task 없을 때 로봇의 기본 동작)

### 상태 모델
- **Robot State (로봇 소유, IF‑02 보고)**: `IDLE PATROL INTERACTING RESERVED HANDOVER_READY ESCORTING WAITING_HANDOVER RETURNING EMERGENCY ERROR`
- **Mission State (FMS 단독 소유)**: `REQUESTED → ASSIGNED → ESCORTING_TO_HANDOVER → HANDOVER_WAITING → ESCORTING_TO_FINAL → COMPLETED` (예외: `CANCELLED/EMERGENCY/FAILED`)

---

## 4. 통합 불변식 (전 트랙 공통 — 위반 시 통합이 깨짐)

역할 경계가 핵심이다. 로봇·FMS 어느 쪽이든 지켜야 한다:

1. **명령은 task로만** — FMS는 목표 상태가 아니라 task(IF‑03)만 보낸다. task가 로봇의 **유일한 외부 입력**.
2. **Robot State는 로봇 소유** — `behavior_node`만 전이·발행(IF‑02). FMS는 관측·검증만.
3. **Mission State는 FMS 소유** — 로봇에 보내지도, 로봇에서 받지도 않는다.
4. **순찰은 task가 아님** — task 없으면 로봇이 스스로 순찰. FMS는 PATROL을 지시하지 않고 관측만.
5. **유닛↔FMS는 MQTT JSON(IF)만** — ROS는 유닛 내부 한정, 변환은 브리지 전담. FMS는 ROS 비의존.
6. **멱등·거절** — QoS1 중복은 `task_id`로 무시. PATROL/IDLE에서 받은 ESCORT task는 REJECT.

> FMS **내부 구현** 규칙(이벤트 구동·블로킹 금지·DB 기록전용·Flask 읽기전용 등 "절대 규칙 8") 전문은 [`docs/FMS_서버_구현가이드.md`](docs/FMS_서버_구현가이드.md)에.

---

## 5. FMS 서버 (`fms_server/`)

> 순수 Python·ROS 비의존. 전체 명령·옵션은 [`fms_server/README.md`](fms_server/README.md) 참조.

### 빠른 실행 (mock으로 실로봇 없이 전체 동작)
```bash
cd fms_server
python3 -m pip install -r requirements.txt
sudo apt-get install -y mosquitto mosquitto-clients && sudo systemctl enable --now mosquitto
python3 tools/build_maps.py          # 맵 png 생성 (최초 1회)

# 터미널 ① FMS
python3 main.py
# 터미널 ②③ 가짜 로봇 2대 (맵 위 좌표 지정)
python3 tools/mock_robot.py --robot-id robot2 --start-x -4.0 --start-y 2.5
python3 tools/mock_robot.py --robot-id robot4 --start-x -1.7 --start-y 2.2
# 터미널 ④ 미션 발생 (Interaction 시뮬)
python3 tools/send_request.py --robot-id robot2 --dest GATE_30 --dest-floor 2 --origin-floor 1
```
**브라우저** `http://localhost:5000/` → 로그인 **`admin` / `admin1234`**

### 자동 검증 (정상3 + 예외4 + 이상1 + API3)
```bash
python3 tools/integration_test.py    # 다른 FMS/로봇은 모두 끈 상태에서
```
> ⚠️ **한 브로커엔 FMS 하나만.** 둘 띄우면 client_id 충돌 + 미션 중복 생성. 테스트 전 `pkill -f main.py`.

### 관제 대시보드
`http://localhost:5000/` — 로그인 후 1초 폴링으로: 로봇 실시간(IF‑02 상태·task·배터리·STALE), 맵 위 로봇 위치(층별 occupancy grid), 활성/최근 미션(전이·핸드오버 지연≤3초), 미션 이력·이상감지(IF‑05), DB 검색.

### 데이터 (SQLite, 기록 전용)
- 위치: `fms_server/fms.db`(+WAL). 런타임 자동 생성. **git 추적 제외**(`.gitignore`).
- 테이블: `requests · missions · mission_transitions · tasks · robot_status_log · events`
- 핸드오버 3초 증빙: `missions.handover_latency_ms`. 집계: `GET /api/stats`. 초기화 = 파일 삭제 후 재기동.

### 환경/설정 (env로 변경)
| 변수 | 기본 | 의미 |
|---|---|---|
| `FMS_MQTT_HOST` | `localhost` | 브로커 주소(로봇은 FMS PC 고정 IP) |
| `FMS_MQTT_PORT` | `1883` | 브로커 포트 |
| `FMS_STATUS_TIMEOUT` | `10` | status 미수신 임계(초) |
| `FMS_FLASK_PORT` | `5000` | 관제/대시보드 포트 |
| `FMS_ADMIN_USER` / `FMS_ADMIN_PASSWORD` | `admin` / `admin1234` | 관제 로그인 |
| `FMS_DB_PATH` | `./fms.db` | SQLite 경로 |

---

## 6. 저장소 구조

```
alfred_ws/                          ← ROS2 워크스페이스 = git 루트 (모노레포)
├── README.md  LICENSE(MIT)  .gitignore
├── src/                            ★ ROS2 트랙 (colcon 빌드 대상)
│   ├── alfred_interfaces/          IF-01~05 커스텀 msg (ament_cmake)
│   ├── alfred_bridge/              fms_bridge_node — ROS↔MQTT/IF 변환 ⭐
│   ├── alfred_interaction/         ui/stt/llm/tts 노드
│   ├── alfred_driving/             behavior_node (+nav2/localization 설정)
│   ├── alfred_vision/              yolo_monitor/video_sender 노드
│   └── alfred_bringup/             unit.launch.py + robot2/robot4 params + maps
├── fms_server/                     ★ FMS 트랙 (순수 Python · 비-ROS)
│   ├── main.py                     조립·기동(MQTT·Flask·타임아웃 감시)
│   ├── config.py transport.py      브로커·토픽·상수 / MQTT 래퍼(paho 격리)
│   ├── state_machine.py            전이표(데이터)
│   ├── mission_manager.py          미션 생성·배정·task 발행·핸드오버·예외
│   ├── robot_registry.py           IF-02 스냅샷·전이감지·미수신 감시
│   ├── event_service.py db.py      IF-05 적재 / SQLite(WAL)
│   ├── api.py  web/                Flask 조회 API + 대시보드(dashboard/login.html)
│   ├── states.py messages.py poi.py  poi_table.yaml
│   └── tools/                      mock_robot · send_request · send_event ·
│                                   watch · build_maps · integration_test · echo_test
└── docs/                           통합 계약·다이어그램·인터페이스 명세
    ├── INTERFACE_CONTRACT.md       ★ 통합 계약 (IF-01~05) — 단일 기준
    ├── bridge_config.template.yaml ★ 브리지 설정 템플릿 (로봇당 복사)
    ├── 인터페이스_정의서_v2_1.md     인터페이스 원본 명세 v2.1
    ├── FMS_서버_구현가이드.md        구현 가이드 (절대 규칙)
    ├── *.png                       아키텍처·배치·노드 다이어그램
    └── maps/                       SLAM 맵 (map_1/2 .pgm+.yaml)
```

빌드 산출물(`build/ install/ log/`), 파이썬 캐시, `fms.db`는 `.gitignore`로 추적 제외.

---

## 7. 진행 상태 · 미확정 사항

| 마일스톤 | 상태 |
|---|---|
| M0~M4 FMS 서버 (인터페이스·미션·핸드오버·예외·관제 대시보드) | ✅ |
| M5 ROS2 워크스페이스 골격 (6 패키지, colcon build 통과) | ✅ |
| **M6 실로봇 통합** | ⏳ 각 트랙 노드 본문 구현 + 브리지 변환 채우기 (mock→실브리지, FMS 코드 무변경 목표) |

**통합 전 확정/확인 필요:**
- **노드 본문 구현** — `src/*` 스텁의 `# TODO` 채우기 (각 트랙)
- **브리지 변환** — `fms_bridge_node`의 msg↔IF JSON 변환 + `bridge_config.template.yaml` 매핑
- **NTP(chrony) 동기화** — 핸드오버 3초 측정 정확도 전제 ⚠️
- **FMS 호스트 고정 IP** — 로봇들이 `FMS_MQTT_HOST` / 브리지 `broker_host`로 지정
- **POI 좌표** — `poi_table.yaml`에 실제 목적지/핸드오버/대기/복귀 지점 입력 (현재 placeholder)

**스코프 아웃(의도적):** 동시 고객 2명 이상·배정 실패 응답·재배정·CHARGING·외부 CCTV 연계. (정의서 부록 C 참조)

---

## 8. 문서 인덱스

| 문서 | 용도 |
|---|---|
| [docs/INTERFACE_CONTRACT.md](docs/INTERFACE_CONTRACT.md) | **통합 계약 IF‑01~05 (전 트랙 필독)** |
| [docs/bridge_config.template.yaml](docs/bridge_config.template.yaml) | 브리지 설정 템플릿 |
| [docs/인터페이스_정의서_v2_1.md](docs/인터페이스_정의서_v2_1.md) | 인터페이스 원본 명세 |
| [docs/FMS_서버_구현가이드.md](docs/FMS_서버_구현가이드.md) | 구현 가이드·절대 규칙 |
| [fms_server/README.md](fms_server/README.md) | FMS 서버 실행·명령 상세 |
| docs/*.png | 아키텍처·배치·노드 다이어그램 |

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
Copyright (c) 2026 ROKEY 7기 지능1 Team Alfred
