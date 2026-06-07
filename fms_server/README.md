# FMS 서버 — 다중 로봇 릴레이 에스코트

교통허브에서 TurtleBot4 2대가 고객을 릴레이로 에스코트하는 시스템의 **중앙 조율 서버(FMS)**.
순수 Python 단일 프로그램 + Mosquitto(MQTT) + SQLite.

> 👉 **통합팀은 먼저 [`../README.md`](../README.md)(핸드오프 개요)부터 읽으세요.** 이 문서는 서버 실행·명령 상세입니다.
> 기준 문서: [`../docs/FMS_서버_구현가이드.md`](../docs/FMS_서버_구현가이드.md), [`../docs/인터페이스_정의서_v2_1.md`](../docs/인터페이스_정의서_v2_1.md)
> 타 트랙 배포용 인터페이스 계약: [`../docs/INTERFACE_CONTRACT.md`](../docs/INTERFACE_CONTRACT.md)

## 설계 원칙 (절대 규칙 8개 — 위반 금지)

1. **ROS 금지** — 로봇과의 통신은 MQTT JSON뿐. rclpy import 금지.
2. **블로킹/폴링 금지** — 이벤트 구동 상태기계. 타임아웃은 감시 스레드(타이머)로.
3. **명령은 task로만** — IF-03 task(4종)만 발행. 목표 상태 전송 금지.
4. **Mission State는 FMS 단독 소유** — 로봇에 전송도, 로봇에게서 수신도 안 함.
5. **Robot State는 로봇 소유** — FMS는 IF-02로 관측만(전이표는 검증용).
6. **DB는 기록 전용** — 컴포넌트 간 통신 수단 금지.
7. **Flask는 읽기 전용** — GET 조회만.
8. **순찰은 task 아님** — FMS는 PATROL을 지시하지 않음.

## 모듈 구조

| 파일 | 책임 | 상태 |
|---|---|---|
| `config.py` | 브로커·토픽·타임아웃 상수·POI 로드 | ✅ M0 |
| `db.py` | SQLite(WAL) 스키마·적재 | ✅ M0 |
| `transport.py` | MQTT 래퍼 (**paho 의존 격리**) | ✅ M0 |
| `poi_table.yaml` | POI 테이블 (값 대기, 구조 스텁) | ✅ M0 |
| `main.py` | 조립·기동 | ✅ M1 |
| `tools/echo_test.py` | M0 pub/sub 왕복 검증 | ✅ M0 |
| `states.py` | Robot/Mission/Task enum 상수 | ✅ M1 |
| `messages.py` | IF-01~05 + task_ack 빌더(공통필드) | ✅ M1 |
| `robot_registry.py` | IF-02 스냅샷·전이 감지·미수신 감시 | ✅ M1 |
| `api.py` | Flask GET 조회 (`/robots`, `/health`) | ✅ M1 |
| `tools/mock_robot.py` | 가짜 로봇 시뮬레이터 (+호출 제어훅) | ✅ M1·M2 |
| `tools/send_request.py` | Interaction 시뮬레이터(IF-01, +취소) | ✅ M2·M3 |
| `tools/send_event.py` | Vision 시뮬레이터(IF-05 발행) | ✅ M4 |
| `tools/watch.py` | 터미널 실시간 대시보드 | ✅ |
| `web/dashboard.html` | **브라우저 관제 대시보드** (Flask `/` 서빙) | ✅ |
| `web/maps/` + `tools/build_maps.py` | **맵 패널** (층별 ROS occupancy grid + 로봇 실시간 위치) | ✅ |
| `event_service.py` | IF-05 이상감지 적재 | ✅ M4 |
| `poi.py` | POI 조회·goal 변환 헬퍼 | ✅ M2 |
| `state_machine.py` | 전이표 코드화(정상+예외 데이터) | ✅ M2·M3 |
| `mission_manager.py` | mission 생성·배정·task 발행·핸드오버 승인·3초 측정·**예외 처리** | ✅ M2·M3 |
| `tools/integration_test.py` | 통합 회귀 테스트(정상 3 + 예외 4) | ✅ M3 |

## 설치 및 실행

```bash
cd fms_server
python3 -m pip install -r requirements.txt

# Mosquitto(MQTT 브로커) 설치·기동
sudo apt-get install -y mosquitto mosquitto-clients
sudo systemctl start mosquitto      # 또는: mosquitto -d

# DB 초기화 (선택 — main 기동 시 자동 생성)
python3 db.py

# M0 에코 테스트
python3 tools/echo_test.py

# FMS 기동 (M1: IF-02 파이프라인 + 조회 API)
python3 main.py
```

### M1 동작 확인 (mock 로봇 + 조회 API)

```bash
# 터미널 1: FMS
python3 main.py

# 터미널 2~3: 가짜 로봇 2대 (실로봇 없이 전체 검증)
python3 tools/mock_robot.py --robot-id robot2
python3 tools/mock_robot.py --robot-id robot4 --rate 5 --task-duration 3

# 터미널 4: 조회
curl http://localhost:5000/api/robots   # 로봇별 최신 IF-02 스냅샷
curl http://localhost:5000/api/health
```

> **Mosquitto 없이 로컬 검증:** 순수 파이썬 브로커 `amqtt`(`pip install amqtt` 후 `amqtt` 실행)로도
> 동일하게 동작한다. 실배포는 Mosquitto를 쓴다.

### M2 전체 릴레이 미션 실행 (호출 → 핸드오버 → 완료)

```bash
# 터미널 1: FMS / 2~3: mock 로봇 2대 (위와 동일하게 기동)

# 터미널 4: Interaction 시뮬레이터로 미션 시작 (robot2 호출 → IF-01 ESCORT)
python3 tools/send_request.py --robot-id robot2 --dest GATE_30 --dest-floor 2 --origin-floor 1
#   같은 층 직행 테스트: --dest-floor 1 --origin-floor 1

# 터미널 5: 결과 조회
curl http://localhost:5000/api/missions
curl http://localhost:5000/api/missions/<mission_id>   # 전이 이력 + tasks + handover_latency_ms
```

전이 흐름: `REQUESTED→ASSIGNED→ESCORTING_TO_HANDOVER→HANDOVER_WAITING→ESCORTING_TO_FINAL→COMPLETED`
(같은 층은 `ASSIGNED→ESCORTING_TO_FINAL→COMPLETED`). `missions.handover_latency_ms`에 3초 측정값 기록.

### 브라우저 관제 대시보드

FMS 기동 후 브라우저에서 **http://localhost:5000/** 접속 (다른 PC면 `http://<FMS_IP>:5000/`).
1초마다 폴링하며 표시: **로봇 실시간(IF-02)** · **맵 위 로봇 위치(층별)** · **활성/최근 미션 + 핸드오버 지연** · **미션 이력** · **이상감지(IF-05)**.
읽기 전용(절대 규칙 7) — 페이지는 `/api/robots·/maps·/missions·/events`만 GET 한다.

**맵 빌드**(최초 1회 / 맵 갱신 시): `python3 tools/build_maps.py` — `docs/maps/*.pgm+yaml` → `web/maps/*.png + maps.json`.
robot2=1층(map_1), robot4=2층(map_2). 로봇 dot은 IF-02 pose를 맵 좌표로 변환해 실시간 표시.
mock으로 맵 위에 띄우려면 시작 좌표 지정: `--start-x -4.0 --start-y 2.5`.

**로그인**: 접속 시 `/login` (기본 `admin` / `admin1234`, env `FMS_ADMIN_USER`·`FMS_ADMIN_PASSWORD`로 변경).
세션 쿠키 기반, 미인증 시 페이지는 `/login`·API는 401. 우상단 "로그아웃".

**검색**: 대시보드 하단 "검색 (DB 기록)" — `GET /api/search?q=&kind=missions|events|tasks|all`로
저장된 미션·이벤트·task를 키워드 조회(읽기 전용).

### 실시간 대시보드로 "움직임" 보기 (터미널 버전)

서버가 어떻게 도는지 눈으로 보려면, 4개 터미널을 띄운다:

```bash
# 터미널 1: FMS
python3 main.py
# 터미널 2~3: 가짜 로봇 2대
python3 tools/mock_robot.py --robot-id robot2
python3 tools/mock_robot.py --robot-id robot4
# 터미널 4: 실시간 대시보드 (0.5초마다 갱신)
python3 tools/watch.py
```

그다음 아무 터미널에서나 미션/이벤트를 일으키면, 대시보드에서 로봇 상태·미션 전이·
핸드오버 지연이 **실시간으로 바뀌는 걸** 본다:

```bash
python3 tools/send_request.py --robot-id robot2 --dest GATE_30 --dest-floor 2 --origin-floor 1
python3 tools/send_event.py   --robot-id robot2 --type FIRE
python3 tools/send_request.py --robot-id robot2 --cancel        # 취소 흐름
```

### 통합 테스트 (한 번에 자동 검증)

브로커만 떠 있으면 M1·M2 전체(IF-02 파이프라인 + 릴레이 + 같은 층 직행)를 자동 검증한다:

```bash
sudo systemctl start mosquitto        # 또는: mosquitto -d / amqtt
python3 tools/integration_test.py
# [정상] 1) IF-02 파이프라인  2) 층간 릴레이(+3초 측정)  3) 같은 층 직행
# [예외] 4) CANCEL  5) EMERGENCY  6) task FAILED  7) status timeout
# [이상] 8) IF-05 FIRE 적재
# [API]  9) /api/robots  10) /api/missions  11) /api/events
# ✅ 통합 테스트 전체 PASS (정상 3 + 예외 4 + 이상감지 1 + 관제 API 3)
```

시뮬레이터 도구:
- `send_request.py` — IF-01 ESCORT / `--cancel` 취소 (Interaction)
- `send_event.py` — IF-05 FIRE/SUSPICIOUS_PERSON (Vision)
- mock 제어 `mock/{id}/cmd`: `{"cmd":"call"|"emergency"|"fail"|"mute"|"recover"}`

## 설정 (환경변수 override)

| 변수 | 기본값 | 의미 |
|---|---|---|
| `FMS_MQTT_HOST` | `localhost` | 브로커 주소 |
| `FMS_MQTT_PORT` | `1883` | 브로커 포트 |
| `FMS_STATUS_TIMEOUT` | `10.0` | robot status 미수신 임계(초) |
| `FMS_DB_PATH` | `./fms.db` | SQLite 경로 |
| `FMS_FLASK_PORT` | `5000` | 조회 API 포트 |

## 마일스톤

- **M0** — 스캐폴드 + 인터페이스 계약 ✅
- **M1** — mock_robot + IF-02 파이프라인 + `GET /api/robots` ✅
- **M2** — 미션 1사이클(전이표) + `handover_latency_ms` 산출 ✅ (같은 층 직행 포함)
- **M3** — 예외(CANCEL/EMERGENCY/FAILED/status timeout) + task REJECT ✅
- **M4** — IF-05 이벤트(FIRE/SUSPICIOUS_PERSON) + 관제 API 마감 ✅
- **M5** — 실로봇 통합(FMS 코드 무변경 목표) ← *남음(월요일, 실로봇/브리지 필요)*
