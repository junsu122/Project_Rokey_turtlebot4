# 다중 로봇 릴레이 에스코트 — FMS 서버 (통합 핸드오프)

> ROKEY 7기 A-2조 · 교통허브 내 다중 AMR 기반 릴레이 에스코트 시스템
> 본 저장소는 **FMS(중앙 관제 서버)** 구현 + 통합에 필요한 계약·도구·문서 일체를 담는다.
> 프로토콜 버전 **v2.1** · 전송 **MQTT** · 2025‑한 줄 요약: *"로봇은 보고하고, FMS는 task를 내린다."*

---

## 0. FMS란?

**FMS = Fleet Management System (다중 로봇 관제·운영 서버).**
여러 대의 로봇(여기선 TurtleBot4 2대)을 **한곳에서 조율**하는 중앙 서버다. 본 프로젝트에서 FMS는:

- 고객 요청(IF‑01)을 받아 **미션을 생성**하고
- 어느 로봇이 출발/인계할지 **배정**하며
- 각 로봇에 **할 일(task, IF‑03)** 을 내리고
- 로봇들의 **상태 보고(IF‑02)** 로 미션 진행을 계산하며 (Mission State는 **FMS만 소유**)
- 층간 **핸드오버를 승인**하고 그 **지연(3초 기준)을 측정**하며
- 이상감지(IF‑05)·이력을 **DB에 기록**하고 **관제 UI**로 보여준다.

FMS는 **로봇의 바퀴를 직접 제어하지 않는다.** "무엇을 하라(task)"만 주고, "어떻게(주행)"는 로봇이 한다.

### 서비스 흐름 (정상 시나리오)
```
고객이 1층 robot2 호출 → robot2가 핸드오버 지점까지 안내
→ 2층 robot4가 이어받아(핸드오버) 최종 목적지까지 안내
(같은 층이면 robot2가 직행)
```

---

## 1. 시스템 아키텍처 (트랙 분업)

4개 트랙이 **정의된 인터페이스(IF‑01~05)** 로만 통신한다.

| 트랙 | 역할 | FMS로 보냄 | FMS에서 받음 |
|---|---|---|---|
| **Interaction** (STT/LLM/TTS/UI) | 고객 응대·목적지 확정 | IF‑01 (요청) | — |
| **Driving/Escort** | 자율주행·핸드오버 수행 | IF‑02 (상태), task_ack | **IF‑03 (task) — 유일 입력** |
| **Vision** | 카메라 YOLO 이상감지 | IF‑05 (이벤트) | — |
| **FMS** (본 저장소) | 미션·상태·핸드오버 조율 | IF‑03 | IF‑01/02/05 |
| **관제 UI** | 모니터링 | — | Flask REST(GET) |

**핵심: FMS는 ROS를 모른다.** 로봇 유닛 내부는 ROS2지만, 유닛↔FMS는 **MQTT JSON(IF)** 한 채널뿐이고, 그 변환은 각 로봇 유닛의 **브리지 노드**가 한다. → 자세한 그림:

- [`docs/SYSTEM_ARCHITECTURE.png`](docs/SYSTEM_ARCHITECTURE.png) — 제어 평면(MQTT/HTTP) + 데이터 평면(영상)
- [`docs/DEPLOYMENT_TOPOLOGY.png`](docs/DEPLOYMENT_TOPOLOGY.png) / [`..._SEPARATED.png`](docs/DEPLOYMENT_TOPOLOGY_SEPARATED.png) — 어느 PC에 무엇이 도나(공유/분리 도메인)
- [`docs/ROBOT_UNIT_NODES.png`](docs/ROBOT_UNIT_NODES.png) — 로봇 유닛 내부 ROS2 노드 구성(참조 제안)

---

## 2. ⭐ 통합팀이 먼저 볼 것 (로봇 측 = 브리지)

FMS는 완성되어 있다. 통합팀의 작업은 **각 로봇 유닛에 브리지 노드를 만들어 ROS ↔ IF/MQTT를 잇는 것**이다.

1. **[`docs/INTERFACE_CONTRACT.md`](docs/INTERFACE_CONTRACT.md)** ← **이 계약이 단일 기준.** IF‑01~05 형식·토픽·QoS·상태 enum·정상/예외 흐름 전부.
2. **[`docs/bridge_config.template.yaml`](docs/bridge_config.template.yaml)** ← 로봇당 이 블록을 복사해 **`ros_topic`/`ros_type` 빈칸만 채우면** 브리지 매핑 완성.
3. 브리지가 할 일(양방향 번역):
   - `ros→mqtt`: 로봇 ROS 토픽 구독 → IF JSON으로 `robot/{id}/status·request·event·task_ack` 발행
   - `mqtt→ros`: `robot/{id}/task`(IF‑03) 구독 → 로봇 ROS 토픽으로 재발행 → Driving 수행

### 브리지 구현 시 필수 규칙
- **멱등**: QoS 1은 중복 배달 가능 → 이미 처리한 `task_id` 재수신 시 무시.
- **거절 규칙(계약 §6.2)**: 로봇이 **PATROL/IDLE**(임무 없이 대기) 상태에서 받은 ESCORT 계열 task는 **REJECT** (유령 에스코트 방지). 임무 중 상태(INTERACTING·RESERVED·HANDOVER_READY·WAITING_HANDOVER·ESCORTING)는 수락.
- **client_id 유일**: 브리지마다 다른 MQTT client_id (`bridge_robot2`, `bridge_robot4`). FMS는 `fms_server`.
- **시간 동기화(NTP)**: 핸드오버 "3초" 측정은 로봇 PC와 FMS PC의 timestamp 차이로 계산 → **전 기기 chrony(NTP) 동기화 필수.**

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

## 4. 설계 원칙 (절대 규칙 8 — 위반 시 통합이 깨짐)

1. **ROS 금지** — FMS는 ROS 비의존, MQTT JSON만.
2. **이벤트 구동** — 블로킹/DB 폴링 금지. 타임아웃은 감시 스레드(타이머)로.
3. **명령은 task로만** — 목표 상태를 보내지 않음.
4. **Mission State는 FMS 단독 소유** — 로봇에 전송도, 로봇에서 수신도 안 함.
5. **Robot State는 로봇 소유** — FMS는 관측만(전이표는 검증용).
6. **DB는 기록 전용** — 통신 수단으로 쓰지 않음.
7. **Flask는 읽기 전용 GET** — 로봇 제어·미션 생성을 HTTP로 받지 않음(로그인 인증은 예외).
8. **순찰은 task가 아님** — FMS는 PATROL을 지시하지 않음.

---

## 5. 빠른 실행 (mock으로 실로봇 없이 전체 동작)

> 전체 명령·옵션은 [`fms_server/README.md`](fms_server/README.md) 참조.

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

---

## 6. 관제 대시보드 (브라우저)

`http://localhost:5000/` — 로그인 후 1초 폴링으로:
- **로봇 실시간(IF‑02)**: 상태·task·배터리·last_seen(STALE 표시)
- **맵 위 로봇 위치**: 층별 ROS occupancy grid + 로봇 dot(IF‑02 pose 변환). robot2=1층, robot4=2층.
- **활성/최근 미션**: 상태·전이·핸드오버 지연(≤3초)·발행 task
- **미션 이력 / 이상감지(IF‑05)**
- **검색(DB)**: 미션·이벤트·task 키워드 조회
- **로그인**: 세션 기반(`admin`/`admin1234`, env로 변경). 미인증 시 페이지→`/login`, API→401.

---

## 7. 데이터 (SQLite, 기록 전용)

- 위치: `fms_server/fms.db` (+ WAL: `fms.db-wal`, `fms.db-shm`). 런타임 자동 생성.
- 테이블: `requests · missions · mission_transitions · tasks · robot_status_log · events`
- 핸드오버 3초 증빙: `missions.handover_latency_ms`. 성능 집계: `GET /api/stats`.
- 백업 = `fms.db` 복사, 초기화 = 파일 삭제 후 재기동.

---

## 8. 저장소 구조

```
alfred_ws/
├── README.md                       ← (이 문서) 통합 핸드오프 개요
├── docs/
│   ├── INTERFACE_CONTRACT.md       ★ 통합 계약 (IF-01~05) — 단일 기준
│   ├── bridge_config.template.yaml ★ 브리지 설정 템플릿 (로봇당 복사)
│   ├── 인터페이스_정의서_v2_1.md     인터페이스 원본 명세 v2.1
│   ├── FMS_서버_구현가이드.md        구현 가이드 (절대 규칙)
│   ├── SYSTEM_ARCHITECTURE.png      제어/데이터 평면 아키텍처
│   ├── DEPLOYMENT_TOPOLOGY*.png     PC 배치(공유/분리 도메인)
│   ├── ROBOT_UNIT_NODES.png         로봇 유닛 ROS2 노드 구성(참조)
│   └── maps/                        SLAM 맵 (map_1/2 .pgm+.yaml, 좌표 png)
└── fms_server/
    ├── README.md                   서버 상세 실행 가이드
    ├── main.py                     조립·기동(MQTT·Flask·타임아웃 감시)
    ├── config.py                   브로커·토픽·상수·로봇 레지스트리·로그인
    ├── transport.py                MQTT 래퍼 (paho 의존 격리)
    ├── states.py messages.py poi.py
    ├── state_machine.py            전이표(데이터)
    ├── mission_manager.py          미션 생성·배정·task 발행·핸드오버·예외
    ├── robot_registry.py           IF-02 스냅샷·전이감지·미수신 감시
    ├── event_service.py db.py      IF-05 적재 / SQLite(WAL)
    ├── api.py                      Flask: 로그인 + 조회 API + 대시보드 서빙
    ├── poi_table.yaml              POI 테이블 (실좌표 대기)
    ├── web/                        dashboard.html · login.html · maps/
    └── tools/                      mock_robot · send_request · send_event ·
                                    watch · build_maps · integration_test · echo_test
```

---

## 9. 환경/설정 (env로 변경)

| 변수 | 기본 | 의미 |
|---|---|---|
| `FMS_MQTT_HOST` | `localhost` | 브로커 주소(로봇은 FMS PC 고정 IP) |
| `FMS_MQTT_PORT` | `1883` | 브로커 포트 |
| `FMS_STATUS_TIMEOUT` | `10` | status 미수신 임계(초) |
| `FMS_FLASK_PORT` | `5000` | 관제/대시보드 포트 |
| `FMS_ADMIN_USER` / `FMS_ADMIN_PASSWORD` | `admin` / `admin1234` | 관제 로그인 |
| `FMS_DB_PATH` | `./fms.db` | SQLite 경로 |

---

## 10. 진행 상태 · 미확정 사항

| 마일스톤 | 상태 |
|---|---|
| M0 스캐폴드 + 인터페이스 계약 | ✅ |
| M1 IF‑02 파이프라인 + 조회 API | ✅ |
| M2 미션 1사이클 + 핸드오버 3초 측정 | ✅ |
| M3 예외(취소·비상·실패·타임아웃) | ✅ |
| M4 IF‑05 + 관제 API + 대시보드(맵·로그인·검색) | ✅ |
| **M5 실로봇 통합** | ⏳ **통합팀 진행** (mock→실브리지 교체, FMS 코드 무변경 목표) |

**통합 전 확정/확인 필요:**
- **브리지 토픽 매핑** — `bridge_config.template.yaml`의 `ros_topic`/`ros_type` 채우기 (로봇 트랙)
- **NTP(chrony) 동기화** — 핸드오버 3초 측정 정확도 전제 ⚠️
- **FMS 호스트 고정 IP** — 로봇들이 `FMS_MQTT_HOST`로 지정
- **POI 좌표** — `poi_table.yaml`에 실제 목적지/핸드오버/대기/복귀 지점 입력 (현재 placeholder). 맵 좌표계는 ROS map 프레임(미터)으로 확정됨.

**스코프 아웃(현 단계 미구현, 의도적):** 동시 고객 2명 이상·배정 실패 응답·재배정·CHARGING·외부 CCTV 연계. (정의서 부록 C 참조)

---

## 11. 문서 인덱스

| 문서 | 용도 |
|---|---|
| [docs/INTERFACE_CONTRACT.md](docs/INTERFACE_CONTRACT.md) | **통합 계약 IF‑01~05 (필독)** |
| [docs/bridge_config.template.yaml](docs/bridge_config.template.yaml) | 브리지 설정 템플릿 |
| [docs/인터페이스_정의서_v2_1.md](docs/인터페이스_정의서_v2_1.md) | 인터페이스 원본 명세 |
| [docs/FMS_서버_구현가이드.md](docs/FMS_서버_구현가이드.md) | 구현 가이드·절대 규칙 |
| [fms_server/README.md](fms_server/README.md) | 서버 실행·명령 상세 |
| docs/*.png | 아키텍처·배치·노드 다이어그램 |
