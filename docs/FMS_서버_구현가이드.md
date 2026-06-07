# FMS 서버 구현 가이드 (Claude Code용)

> 이 문서는 **FMS 서버 구현 작업의 단일 기준 문서**다.
> 반드시 `인터페이스_정의서_v2_1.md`(인터페이스 계약·상태 모델·전이표 원본)와 함께 읽는다.
> 두 문서가 충돌하면 인터페이스 정의는 v2.1이, 서버 구현 방식은 본 문서가 우선한다.

## 0. 프로젝트 컨텍스트 (1분 요약)

교통허브에서 TurtleBot4 두 대(로봇 A=1층, B=2층)가 고객을 릴레이로 에스코트하는 시스템.
고객이 로봇 A에게 목적지를 말하면 → A가 핸드오버 지점까지 안내 → 2층의 B가 이어받아 최종 목적지까지 안내.
FMS는 이 전체를 조율하는 중앙 서버다. 지금 만드는 것이 이 FMS다.

- 로봇 유닛 = TurtleBot4(RPi4) + 탑재 노트북. 유닛 내부는 ROS 2, 유닛↔FMS는 MQTT JSON.
- 각 노트북의 "브리지 노드"가 ROS↔MQTT 변환 담당 (브리지는 로봇 트랙 소관, FMS 구현 범위 아님).
- 시연 전제: 동시 고객 1명, 미션당 로봇 2대 전속, Wi-Fi 안정 가정.

## 1. 구현 범위와 기술 스택

**FMS 서버 = 순수 Python 단일 프로그램** + 같은 PC에서 도는 인프라 2종.

| 구성요소 | 형태 | 비고 |
|---|---|---|
| fms_server | Python 패키지 (직접 구현) | 본 문서의 대상 |
| Mosquitto | 설치형 MQTT 브로커 | localhost:1883, 코드 아님 |
| chrony | NTP 서버 | 전 기기 시간 동기화용, 코드 아님 |

- Python 3.10+, 외부 의존성: `paho-mqtt`, `flask` (+표준 라이브러리 sqlite3). 최소로 유지.
- DB: SQLite, WAL 모드.

## 2. 절대 규칙 (위반 시 설계 전체가 무너짐)

1. **ROS 금지.** rclpy import 금지, ROS 설치 가정 금지. FMS는 ROS의 존재를 모른다. 로봇과의 모든 통신은 MQTT JSON뿐이다.
2. **블로킹 대기 금지.** "로봇 도착까지 기다리는" 절차적 시나리오 함수를 만들지 않는다. FMS는 **이벤트 구동 상태 기계**다: MQTT 메시지가 오면 핸들러가 현재 상태를 보고 전이·task 발행을 수행하고 즉시 리턴한다. `time.sleep()`으로 흐름을 잡는 코드, "wait until state==X" 루프는 금지. (타임아웃 감시는 sleep이 아니라 타이머/주기 체크 스레드로.)
3. **명령은 task로만.** 로봇에게 "목표 상태"나 "목표 Mission State"를 보내지 않는다. IF-03 task(task_id, task_type, goal, mission_id)만 발행한다.
4. **Mission State는 FMS 단독 소유.** 로봇에게 전송하지 않고, 로봇이 보고하는 값으로 받지도 않는다. 로봇이 보고하는 것은 Robot State뿐이다.
5. **Robot State는 로봇 소유.** FMS는 IF-02로 관측만 한다. 전이표의 "기대 Robot State"는 검증(어긋나면 경고 로그)용이지 명령이 아니다.
6. **DB는 기록 전용.** DB를 컴포넌트 간 통신 수단으로 쓰지 않는다 (예: "로봇이 DB에 쓰고 FMS가 폴링" 금지). 모든 실시간 흐름은 MQTT, DB는 결과 적재만.
7. **Flask는 읽기 전용.** GET 조회 API만. 로봇 제어·미션 생성을 HTTP로 받지 않는다.
8. **순찰은 task가 아니다.** FMS는 PATROL을 지시하지 않는다. task 없는 로봇이 스스로 순찰하며, FMS는 IF-02의 state=PATROL을 관측할 뿐이다.

## 3. 프로세스·모듈 구조

```
fms_server/
├── main.py            # 조립·기동 (mqtt 연결, flask 스레드, 타임아웃 감시 스레드)
├── config.py          # 브로커 주소, 토픽, 타임아웃 상수, POI 테이블 로드
├── poi_table.yaml     # poi_id → {표시명, floor, pose(x,y,theta)}, 핸드오버/대기/복귀 지점 포함
├── transport.py       # MQTT 클라이언트 래퍼 (이 파일에만 paho-mqtt 의존 격리)
├── mission_manager.py # mission 생성, start/next_robot 배정, task 생성·발행, task_id/ack 추적
├── state_machine.py   # Mission FSM: (현재 Mission State, 이벤트) → 전이 + 액션. 전이표의 코드화
├── robot_registry.py  # 로봇별 최신 IF-02 스냅샷, 전이 감지, 미수신(통신장애) 감시
├── db.py              # SQLite 스키마 생성·적재 (WAL)
└── api.py             # Flask GET 엔드포인트 (읽기 전용)
```

설계 의도:
- **transport.py에 전송 계층 격리.** 프로토콜이 공식 미확정(MQTT 권장안)이므로, publish/subscribe 인터페이스를 클래스로 감싸 다른 프로토콜로의 교체 가능성을 남긴다. 다른 모듈은 paho를 직접 import하지 않는다.
- **state_machine.py가 두뇌.** 전이를 데이터(표)로 들고, 이벤트 핸들러는 "표 조회 → 상태 갱신 → 액션 실행(task 발행, DB 기록)"만 한다.
- 동시 고객 1명 전제이므로 활성 mission은 최대 1개. 단, 코드 구조는 mission_id 기준으로 짜서(전역 변수 금지) 확장 여지를 남긴다.

## 4. MQTT 채널 명세

브로커: localhost:1883 (로봇들은 FMS PC의 고정 IP로 접속).

| 토픽 | 방향 | 페이로드 | QoS | FMS 동작 |
|---|---|---|---|---|
| robot/{id}/status | 로봇→FMS | IF-02 | 0 | robot_registry 갱신, 전이 시 FSM 이벤트 발생 |
| robot/{id}/request | 로봇→FMS | IF-01 | 1 | mission 생성/취소 처리 |
| robot/{id}/event | 로봇→FMS | IF-05 | 1 | DB 적재, 관제 노출 |
| robot/{id}/task | FMS→로봇 | IF-03 | 1 | mission_manager가 발행 |
| robot/{id}/task_ack | 로봇→FMS | ACK | 1 | task 수락/거절 확인 |

{id} ∈ {A, B}. FMS는 `robot/+/status` 식 와일드카드로 일괄 구독.

- **멱등:** QoS 1은 중복 배달 가능. FMS는 처리한 msg_id/task_ack를 기억하고 재수신 시 무시한다. (로봇 측 task_id 멱등은 로봇 트랙 소관)
- ACK 타임아웃·재전송 정책은 스코프 아웃 (Wi-Fi 안정 가정, Interaction 측 로컬 타임아웃이 최후 방어선 — v2.1 §2.2).

### 4.1 페이로드 스키마 (v2.1 §2~5와 동일, 구현 시 이대로)

공통 필드: `msg_id`(uuid), `version`("2.1"), `timestamp`(ISO 8601, ms 포함).

**IF-01 (request_type: ESCORT | CANCEL):**
```json
{"msg_id":"...","version":"2.1","request_id":"REQ_0012","robot_id":"A",
 "request_type":"ESCORT",
 "destination":{"poi_id":"GATE_30","floor":2},
 "origin":{"floor":1,"pose":{"x":0.0,"y":0.0}},
 "customer":{"customer_id":"C_xxx","profile":"ELDERLY","language":"ko"},
 "target_request_id":null,
 "timestamp":"..."}
```
poi_id는 Interaction이 검증 완료한 값 — FMS는 유효하다고 신뢰한다 (poi_table에 없으면 버그이므로 ERROR 로그 후 무시).

**IF-02:**
```json
{"msg_id":"...","version":"2.1","robot_id":"A","state":"ESCORTING",
 "pose":{"x":0.0,"y":0.0,"theta":0.0},"battery":78,
 "current_task_id":"TASK_0034","task_status":"RUNNING","error_code":null,
 "timestamp":"..."}
```
state ∈ IDLE|PATROL|INTERACTING|RESERVED|HANDOVER_READY|ESCORTING|WAITING_HANDOVER|RETURNING|EMERGENCY|ERROR
task_status ∈ ACCEPTED|RUNNING|SUCCEEDED|FAILED|null. current_task_id null = 기본동작(순찰/대기) 중.

**IF-03:**
```json
{"msg_id":"...","version":"2.1","task_id":"TASK_0034","robot_id":"B",
 "task_type":"MOVE_TO_STANDBY",
 "goal":{"poi_id":"ES_03","pose":{"x":0.0,"y":0.0},"floor":2},
 "customer":{"customer_id":"C_xxx","profile":"ELDERLY","language":"ko"},
 "mission_id":"MISSION_0012","cancel_task_id":null,"timestamp":"..."}
```
task_type ∈ MOVE_TO_STANDBY | ESCORT_TO_HANDOVER | ESCORT_TO_FINAL | RETURN_TO_BASE (PATROL 없음 — 절대 규칙 8).

**task_ack:** `{"msg_id":"...","task_id":"TASK_0034","robot_id":"B","result":"ACCEPT","timestamp":"..."}` (result: ACCEPT|REJECT)

**IF-05:** `{"msg_id":"...","event_type":"FIRE","robot_id":"A","confidence":0.91,"location":{"x":0,"y":0,"floor":1},"snapshot_ref":"...","timestamp":"..."}` (event_type: FIRE|SUSPICIOUS_PERSON)

## 5. 상태 기계 명세 (구현의 핵심)

Mission State: `REQUESTED, ASSIGNED, ESCORTING_TO_HANDOVER, HANDOVER_WAITING, ESCORTING_TO_FINAL, COMPLETED, CANCELLED, EMERGENCY, FAILED`
(PATROL·INTERACTING 없음 — mission은 IF-01 ESCORT 수신 시 생성)

이벤트 소스는 두 가지: ① IF-01 수신, ② IF-02에서 감지된 Robot State 전이 / task_status 변화. (③ 타임아웃 감시 스레드)

### 5.1 정상 전이 (v2.1 §7 전이표의 코드화 기준)

| 이벤트 | guard | Mission 전이 | 액션 (task 발행 등) |
|---|---|---|---|
| IF-01 ESCORT 수신 | 활성 mission 없음 | (생성) → REQUESTED | mission_id 채번, DB 기록 |
| (즉시 이어서) 배정 | dest.floor ≠ origin.floor | REQUESTED → ASSIGNED | start=호출 로봇, next=상대 로봇 결정 / next에 MOVE_TO_STANDBY(대기지점) / start에 ESCORT_TO_HANDOVER(핸드오버 지점) / mission → ESCORTING_TO_HANDOVER |
| (즉시 이어서) 배정 | dest.floor == origin.floor | REQUESTED → ASSIGNED → ESCORTING_TO_FINAL | start에 ESCORT_TO_FINAL(최종 목적지). next 없음, 핸드오버 단계 생략 |
| next: MOVE_TO_STANDBY SUCCEEDED (IF-02) | — | 변화 없음 | next_ready=true 기록. 승인 조건 평가 |
| start: ESCORT_TO_HANDOVER SUCCEEDED (IF-02, state→WAITING_HANDOVER) | — | ESCORTING_TO_HANDOVER → HANDOVER_WAITING | start_arrived=true + **t_arrival 기록(3초 측정 시작)**. 승인 조건 평가 |
| **핸드오버 승인**: start_arrived ∧ next_ready | 도착 순서 무관 | HANDOVER_WAITING → ESCORTING_TO_FINAL | next에 ESCORT_TO_FINAL / start에 RETURN_TO_BASE / **t_pickup_cmd 기록, (t_pickup_cmd − t_arrival) 핸드오버 지연으로 DB 저장** |
| start: RETURN_TO_BASE SUCCEEDED | — | 변화 없음 | 로그 |
| next: ESCORT_TO_FINAL SUCCEEDED | — | ESCORTING_TO_FINAL → COMPLETED | next에 RETURN_TO_BASE, mission 종료 DB 기록 |
| next: RETURN_TO_BASE SUCCEEDED | — | (COMPLETED 유지) | 종료 로그 |

주의: 승인 조건은 "둘 다 충족" 평가 함수 하나로 두고, 두 SUCCEEDED 이벤트 핸들러가 각각 호출한다 (A 먼저/B 먼저 모두 동작).

### 5.2 예외 전이

| 이벤트 | Mission 전이 | 액션 |
|---|---|---|
| IF-01 CANCEL 수신 | 진행 중 → CANCELLED | 진행 중 task에 cancel_task_id 발행 + 관련 로봇에 RETURN_TO_BASE |
| IF-02 state=EMERGENCY | 진행 중 → EMERGENCY | 다른 로봇 task 취소+복귀, event_log 기록, 관제 노출 |
| IF-02 task_status=FAILED | 진행 중 → FAILED | 관련 로봇에 RETURN_TO_BASE, 실패 사유 기록 |
| task_ack REJECT | 진행 중 → FAILED | (시연 전제상 재배정 없음 — 부록 C 스코프 아웃) 로그 |
| robot status 미수신 > STATUS_TIMEOUT(기본 10s) | 진행 중 → FAILED, 해당 로봇 ERROR 표기 | 통신장애 로그 |
| 비상 복구 (관제, 추후) | EMERGENCY → 종결 | 복구 로그 |

타임아웃 상수는 config.py에 모은다: STATUS_TIMEOUT=10s, TASK_ACK_TIMEOUT(로깅용)=3s 등. 값은 통합 때 조정.

## 6. DB 스키마 (SQLite, WAL)

```sql
CREATE TABLE requests (request_id TEXT PRIMARY KEY, robot_id TEXT, request_type TEXT,
  payload_json TEXT, received_at TEXT);
CREATE TABLE missions (mission_id TEXT PRIMARY KEY, request_id TEXT, state TEXT,
  start_robot TEXT, next_robot TEXT, dest_poi TEXT, customer_profile TEXT,
  created_at TEXT, completed_at TEXT, handover_latency_ms INTEGER);
CREATE TABLE mission_transitions (id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT,
  from_state TEXT, to_state TEXT, trigger TEXT, at TEXT);
CREATE TABLE tasks (task_id TEXT PRIMARY KEY, mission_id TEXT, robot_id TEXT, task_type TEXT,
  goal_poi TEXT, issued_at TEXT, ack TEXT, ack_at TEXT, final_status TEXT, finished_at TEXT);
CREATE TABLE robot_status_log (id INTEGER PRIMARY KEY AUTOINCREMENT, robot_id TEXT,
  state TEXT, prev_state TEXT, task_id TEXT, task_status TEXT, battery INTEGER,
  x REAL, y REAL, at TEXT);          -- 전이/변화 시에만 INSERT (1~2Hz 주기 보고는 메모리 최신값만)
CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, robot_id TEXT,
  confidence REAL, x REAL, y REAL, floor INTEGER, snapshot_ref TEXT, at TEXT);
```

용도: 통합 디버깅 블랙박스 / 핸드오버 3초 증빙(handover_latency_ms) / 관제 이력 / FMS 재시작 시 미완료 mission 발견 → 관련 로봇에 RETURN_TO_BASE 발행 후 FAILED 처리(안전 복귀 수준만, 미션 이어가기는 구현하지 않음).

## 7. Flask API (읽기 전용, 별도 스레드)

| 엔드포인트 | 응답 |
|---|---|
| GET /api/robots | 로봇별 최신 스냅샷 [{robot_id, state, pose, battery, current_task_id, last_seen}] |
| GET /api/missions?limit=20 | 미션 목록(최신순) + 현재 활성 미션 |
| GET /api/missions/{id} | 미션 상세 + 전이 이력 + tasks |
| GET /api/events?limit=50 | IF-05 이벤트 목록 |

CORS 허용, JSON 응답. 인증 없음(시연 LAN 전제).

## 8. 개발 순서 (마일스톤)

- **M0 — 에코 테스트:** Mosquitto 기동, transport.py로 임의 토픽 pub/sub 왕복 확인.
- **M1 — 가짜 로봇:** `tools/mock_robot.py` 작성 (robot_id 인자, IF-02를 1Hz 발행, robot/{id}/task 구독 → ACCEPT ack 후 N초 뒤 task_status=SUCCEEDED + 해당 상태 전이를 보고하는 단순 시뮬레이터). **실로봇 없이 FMS 전체를 검증하는 핵심 도구이므로 FMS 본체보다 먼저/같이 만든다.**
- **M2 — IF-02 파이프라인:** 수신 → registry 갱신 → 전이 감지 → DB 적재. GET /api/robots 동작.
- **M3 — 미션 한 사이클:** mock 로봇 2대 띄우고 IF-01 발행 → 배정 → 핸드오버 승인 → COMPLETED까지 §5.1 전이가 로그·DB에 정확히 남는지. handover_latency_ms 산출 확인.
- **M4 — 예외:** CANCEL, EMERGENCY, FAILED, status 미수신 각 1케이스. 같은 층 직행 케이스.
- **M5 — 실로봇 통합:** mock을 실제 브리지로 교체. (FMS 코드 변경 없이 되는 것이 목표)

## 9. 미확정·스코프 아웃 (구현하지 말 것 / 바뀔 수 있는 것)

- 전송 프로토콜은 공식 "MQTT 권장·미확정" — MQTT로 구현하되 transport.py에 격리.
- 배정 실패 응답(IF-01 응답 메시지)·task 재배정: 스코프 아웃 (v2.1 부록 C). REJECT는 FAILED 처리로 끝.
- CHARGING, CCTV 연계, 고객 인식(CUSTOMER_DETECTED): 스코프 아웃.
- 좌표계: pose는 각 층 맵 기준. poi_table.yaml의 값은 맵 작성 후 채움(자리만 마련).
