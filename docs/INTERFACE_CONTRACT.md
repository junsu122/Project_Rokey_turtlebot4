# FMS 인터페이스 계약 (IF-01 ~ IF-05) — v2.1

> **이 문서는 FMS가 확정한 인터페이스 계약의 단일 기준이며, 타 트랙(Interaction / Driving / Vision / 관제 UI)은 이 형식에 맞춘다.**
> 원본 설계: [`인터페이스_정의서_v2_1.md`](인터페이스_정의서_v2_1.md), 구현 방식: [`FMS_서버_구현가이드.md`](FMS_서버_구현가이드.md).
> 충돌 시 인터페이스 의미는 정의서, 전송/토픽/버전 등 구현 사항은 본 문서가 우선.
>
> 작성: 2026-06-06 · 프로토콜 버전 `"2.1"` · 전송: **MQTT** (Mosquitto, `localhost:1883`)

---

## 0. 소유권 원칙 (반드시 숙지)

이 4개를 어기면 통합이 무너진다.

1. **Robot State는 로봇이 소유한다.** 모든 상태 전이는 로봇이 스스로 수행하고 IF-02로 보고한다. FMS는 상태를 **명령하지 않는다.**
2. **Mission State는 FMS가 단독 소유한다.** 로봇은 Mission State를 **보고하지도, 알지도 못한다.** FMS가 IF-02들을 근거로 계산한다.
3. **명령은 task(IF-03)로만 한다.** FMS는 "무엇을 하라(task)"를 내리고, 로봇은 "무엇을 하고 있다(state)"와 "task가 어떻게 됐다(task_status)"를 보고한다.
4. **순찰은 task가 아니라 기본 동작이다.** 로봇은 활성 task가 없으면 스스로 PATROL한다. FMS는 지시하지 않고 관측만 한다. 순찰 중 `current_task_id = null`.

> driving 트랙 한 줄 계약: **"task가 있으면 task를 수행하고, 없으면 순찰한다. 어느 쪽이든 상태는 IF-02로 보고한다."**

---

## 1. 전송 계층 (MQTT)

- 브로커: **Mosquitto**, FMS PC 고정 IP의 `:1883`. 로봇 노트북의 브리지 노드가 ROS 토픽 ↔ MQTT JSON 변환.
- FMS는 ROS를 모른다. 로봇↔FMS는 **MQTT JSON 단일 채널**.
- 페이로드는 UTF-8 JSON. `ensure_ascii=False` (한글 그대로).

### 1.1 로봇 식별자 · ROS 도메인/네임스페이스 매핑

**`robot_id`는 ROS 네임스페이스와 동일한 물리 식별자를 쓴다** (번역 레이어 제거 → 버그 지점 감소).
모든 IF 메시지의 `robot_id`, 모든 토픽의 `{id}`는 아래 값이다.

| `robot_id` | ROS namespace | ROS_DOMAIN_ID (현재) | ROS_DOMAIN_ID (분리 후) | MQTT 토픽 접두 |
|---|---|---|---|---|
| `robot2` | `/robot2` | **2 (공유)** | 개별 값(예: 1) | `robot/robot2/...` |
| `robot4` | `/robot4` | **2 (공유)** | 개별 값(예: 2) | `robot/robot4/...` |

> **현재 상황(~월요일 전):** 도메인 분리가 불가하여 두 로봇 모두 `ROS_DOMAIN_ID=2`를 공유하고, ROS 그래프 충돌은 네임스페이스(`robot2`/`robot4`)로 회피한다.
>
> **도메인 분리 시:** `ROS_DOMAIN_ID`는 **DDS(ROS 내부) 디스커버리만** 분할하며 MQTT(브로커 TCP)와 무관하다. 따라서 분리는 **브리지 노드의 환경변수 변경**으로 끝나고, **MQTT 토픽·페이로드·FMS 코드는 그대로다.** `ros_domain_id`는 FMS가 사용하지 않는 정보 값으로, 브리지/도구 실행의 단일 출처로만 둔다.

- **start_robot / next_robot은 식별자가 아니라 미션별 역할이다.** 호출받은 로봇이 그 미션의 start, 상대 로봇이 next. FMS가 동적으로 배정한다.

### 1.2 토픽 명세

`{id} ∈ {robot2, robot4}`. FMS는 `robot/+/...` 와일드카드로 일괄 구독한다.

| 토픽 | 방향 | 메시지 | QoS | 비고 |
|---|---|---|---|---|
| `robot/{id}/status`   | 로봇 → FMS | IF-02 | 0 | 주기 보고(유실 허용) |
| `robot/{id}/request`  | 로봇 → FMS | IF-01 | 1 | 미션 생성/취소 |
| `robot/{id}/event`    | 로봇 → FMS | IF-05 | 1 | 이상 상황 알림 |
| `robot/{id}/task`     | FMS → 로봇 | IF-03 | 1 | **로봇의 유일한 입력 채널** |
| `robot/{id}/task_ack` | 로봇 → FMS | ACK   | 1 | task 수락/거절 |

### 1.3 배달 보장 · 멱등 (정의서 §9.1)

- QoS 1은 중복 배달이 가능하다 → **수신 측은 이미 처리한 `msg_id`(FMS) / `task_id`(로봇)를 기억하고 재수신 시 무시한다.**
- ACK 타임아웃·재전송 정책은 스코프 아웃(Wi-Fi 안정 가정). FMS 무응답의 최후 방어선은 Interaction 로컬 타임아웃(§6.1).

---

## 2. 공통 필드

모든 메시지에 포함한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `msg_id`   | string(uuid) | 메시지 고유 ID (멱등 키) |
| `version`  | string | 프로토콜 버전. **현재 `"2.1"`** |
| `timestamp`| string | ISO 8601, **밀리초 포함** (예: `2026-06-06T14:32:01.123+00:00`). 전 기기 NTP 동기화 전제 |

---

## 3. 상태 enum

### 3.1 Robot State (로봇 소유, IF-02로 보고) — 10종

`IDLE`, `PATROL`, `INTERACTING`, `RESERVED`, `HANDOVER_READY`, `ESCORTING`, `WAITING_HANDOVER`, `RETURNING`, `EMERGENCY`, `ERROR`

### 3.2 Mission State (FMS 단독 소유, 로봇은 모름) — 9종

`REQUESTED → ASSIGNED → ESCORTING_TO_HANDOVER → HANDOVER_WAITING → ESCORTING_TO_FINAL → COMPLETED`
예외: `CANCELLED` / `EMERGENCY` / `FAILED`

> ⚠️ `PATROL`·`INTERACTING`은 Mission State가 **아니다**(로봇의 영역). mission은 IF-01 ESCORT 수신 시 생성된다.

---

## 4. IF-01 — 고객 요청 (Interaction → FMS) · `robot/{id}/request` · QoS 1

목적: Interaction이 파악한 고객 요구를 FMS에 전달. 판단·할당은 FMS.

```json
{
  "msg_id": "uuid-...",
  "version": "2.1",
  "request_id": "REQ_0012",
  "robot_id": "robot2",
  "request_type": "ESCORT",
  "destination": { "poi_id": "GATE_30", "floor": 2 },
  "origin": { "floor": 1, "pose": { "x": 0.0, "y": 0.0 } },
  "customer": { "customer_id": "C_xxx", "profile": "ELDERLY", "language": "ko" },
  "target_request_id": null,
  "timestamp": "2026-06-06T14:32:01.123+00:00"
}
```

| 필드 | 설명 |
|---|---|
| `request_type` | `ESCORT` \| `CANCEL` |
| `destination.poi_id` | LLM이 정규화한 POI ID. 좌표/층 조회는 FMS POI 테이블 담당 |
| `origin.floor` | 출발 가상층. 같은 층 직행 판정(`dest.floor == origin.floor`)에 사용 |
| `customer.profile` | `GENERAL` \| `ELDERLY` \| `FOREIGNER` \| `VISUALLY_IMPAIRED` — 주행 파라미터 반영 |
| `customer.language` | 도착 측 로봇 인사말용 |
| `target_request_id` | (CANCEL 시) 취소할 원 요청 ID |

- **IF-01은 유효한 목적지가 확정된 경우에만 발행한다.** poi_id 유효성 검증은 **Interaction 책임**(§6.2). FMS는 유효하다고 신뢰한다(없으면 ERROR 로그 후 무시).

---

## 5. IF-02 — 로봇 상태 보고 (Robot → FMS) · `robot/{id}/status` · QoS 0

목적: 로봇의 현재 상태 + 수행 중 task 결과 보고. **task 결과 보고 채널을 겸한다**(별도 결과 메시지 없음).

```json
{
  "msg_id": "uuid-...",
  "version": "2.1",
  "robot_id": "robot2",
  "state": "ESCORTING",
  "pose": { "x": 0.0, "y": 0.0, "theta": 0.0 },
  "battery": 78,
  "current_task_id": "TASK_0034",
  "task_status": "RUNNING",
  "error_code": null,
  "timestamp": "2026-06-06T14:32:01.123+00:00"
}
```

| 필드 | 설명 |
|---|---|
| `state` | §3.1 Robot State |
| `current_task_id` | 수행 중 task. **`null` = 기본 동작(순찰/대기) 중** |
| `task_status` | `ACCEPTED` \| `RUNNING` \| `SUCCEEDED` \| `FAILED` \| `null` |
| `error_code` | 오류 코드(정상 시 `null`) |

**발행 규칙:** 1~2 Hz 주기 발행 **+ 상태 전이 / task_status 변화 시 즉시 발행.**
→ 즉시 발행은 **핸드오버 3초 측정의 전제**다(수락 기준). WAITING_HANDOVER 전이는 도착 즉시 보고할 것.

---

## 6. IF-03 — 임무 할당 (FMS → Robot) · `robot/{id}/task` · QoS 1

목적: FMS가 전이표에 따라 로봇에 task 발행. **로봇이 외부에서 받는 유일한 입력 채널.**

```json
{
  "msg_id": "uuid-...",
  "version": "2.1",
  "task_id": "TASK_0034",
  "robot_id": "robot4",
  "task_type": "MOVE_TO_STANDBY",
  "goal": { "poi_id": "STANDBY_2", "pose": { "x": 0.0, "y": 0.0 }, "floor": 2 },
  "customer": { "customer_id": "C_xxx", "profile": "ELDERLY", "language": "ko" },
  "mission_id": "MISSION_0012",
  "cancel_task_id": null,
  "timestamp": "2026-06-06T14:32:01.123+00:00"
}
```

### 6.1 task_type (4종) — PATROL 없음

| task_type | 의미 | 도착 후 로봇 동작 |
|---|---|---|
| `MOVE_TO_STANDBY`    | 고객 없이 지정 지점 이동·**대기** | `HANDOVER_READY`로 후속 task 대기 |
| `ESCORT_TO_HANDOVER` | 고객 동반, 핸드오버 지점까지 안내 | `WAITING_HANDOVER`로 대기 |
| `ESCORT_TO_FINAL`    | 고객 동반, 최종 목적지까지 안내 | task 종료(mission 완료 보고) |
| `RETURN_TO_BASE`     | 임무 종료 후 복귀 | task **완전 종료** → 기본 동작(순찰) 복귀 |

- task는 **역할 중립**으로 정의된다. "누가 받느냐"는 FMS 발행 로직의 몫.
- 취소: `cancel_task_id`에 취소 대상 task_id를 담아 발행 → 로봇은 해당 task 중단 후 후속 task(보통 `RETURN_TO_BASE`) 수행.

### 6.2 task_ack (Robot → FMS) · `robot/{id}/task_ack` · QoS 1

```json
{
  "msg_id": "uuid-...",
  "version": "2.1",
  "task_id": "TASK_0034",
  "robot_id": "robot4",
  "result": "ACCEPT",
  "timestamp": "2026-06-06T14:32:01.123+00:00"
}
```

`result`: `ACCEPT` | `REJECT`. 이후 진행 상황은 IF-02 `task_status`로 보고.

> **거절 규칙 (driving 필수 구현):** 로봇은 자신이 **`PATROL`/`IDLE`(임무 없이 복귀·대기) 상태에서** 받은 ESCORT 계열(`ESCORT_TO_HANDOVER`/`ESCORT_TO_FINAL`) task를 **거절(`REJECT`)** 한다 — FMS 무응답 타임아웃 직후 뒤늦게 도착한 task로 인한 "유령 에스코트" 방지(정의서 §2.2).
>
> ⚠️ 임무 중 상태(`INTERACTING`·`RESERVED`·`HANDOVER_READY`·`WAITING_HANDOVER`·`ESCORTING`)에서는 **수락**한다. 특히 `next_robot`은 핸드오버 후 `HANDOVER_READY` 상태에서 `ESCORT_TO_FINAL`을 받으므로 거절 대상이 아니다. (거절 기준은 "ESCORT 계열이 아닌가"가 아니라 "**지금 임무가 없는 PATROL/IDLE인가**"이다.)

---

## 7. IF-05 — 이상 상황 알림 (Robot → FMS/관제) · `robot/{id}/event` · QoS 1

목적: 순찰 중 **로봇 탑재 카메라 CV(YOLO)**가 감지한 이상 상황. 외부 CCTV 아님.

```json
{
  "msg_id": "uuid-...",
  "version": "2.1",
  "event_type": "FIRE",
  "robot_id": "robot2",
  "confidence": 0.91,
  "location": { "x": 0.0, "y": 0.0, "floor": 1 },
  "snapshot_ref": "img_20260606_1432.jpg",
  "timestamp": "2026-06-06T14:32:01.123+00:00"
}
```

`event_type`: `FIRE` | `SUSPICIOUS_PERSON`. `snapshot_ref`는 참조 키만(원본 영상/이미지는 FMS DB에 저장하지 않음).

---

## 8. 트랙별 입출력 요약

| 트랙 | FMS로 보냄(발행) | FMS에서 받음(구독) |
|---|---|---|
| **Interaction** (STT/LLM/TTS/UI) | IF-01 (`robot/{id}/request`) | — (로컬 타임아웃으로 자기 로봇 ESCORTING 전이 관찰) |
| **Driving/Escort** | IF-02 (`robot/{id}/status`), task_ack | **IF-03 (`robot/{id}/task`) — 유일 입력** |
| **Vision 모니터링** | IF-05 (`robot/{id}/event`) | — |
| **관제 UI** | — | Flask REST (GET, 별도) |

> Interaction의 **FMS 무응답 감지**: IF-01 발행 후 5초 내 자기 로봇의 `INTERACTING → ESCORTING` 전이를 로컬 토픽으로 관찰. 미관찰 시 고객 안내 후 종료, 동일 `request_id` 재사용 금지(재시도 시 새 ID).

---

## 9. 정상 흐름 예시 (층간 릴레이 1사이클)

`robot2` 호출 → GATE_30(2층) 에스코트. 이 미션에서 **robot2=start, robot4=next**.
`→` 발행, `◀` 수신 기준은 **FMS 시점**.

```
1.  ◀ IF-01 ESCORT {robot_id:robot2, dest:GATE_30/2, origin:1}      → mission 생성: REQUESTED
2.    FMS: start=robot2, next=robot4 결정                            → ASSIGNED
3.  → IF-03 MOVE_TO_STANDBY    to robot4 (goal: STANDBY_2)
    → IF-03 ESCORT_TO_HANDOVER to robot2 (goal: HANDOVER_1_2)        → ESCORTING_TO_HANDOVER
4.  ◀ task_ack ACCEPT (robot2), (robot4)
5.  ◀ IF-02 {robot4, state:HANDOVER_READY,  task_status:SUCCEEDED}   → next_ready = true
6.  ◀ IF-02 {robot2, state:WAITING_HANDOVER, task_status:SUCCEEDED}  → HANDOVER_WAITING, t_arrival 기록
7.    FMS: 승인 조건(robot2.WAITING_HANDOVER ∧ robot4.HANDOVER_READY) 충족
    → IF-03 ESCORT_TO_FINAL to robot4 (goal: GATE_30)               → ESCORTING_TO_FINAL
    → IF-03 RETURN_TO_BASE  to robot2 (goal: BASE_A)
       t_pickup_cmd 기록 → handover_latency_ms = t_pickup_cmd − t_arrival  (≤ 3000ms 목표)
8.  ◀ IF-02 {robot2, state:RETURNING→PATROL}                        (로그)
9.  ◀ IF-02 {robot4, state:RETURNING, task_status:SUCCEEDED}         → COMPLETED
    → IF-03 RETURN_TO_BASE to robot4 (goal: BASE_B)
10. ◀ IF-02 {robot4, state:PATROL}                                  mission 종료 로그
```

**같은 층 직행**(`dest.floor == origin.floor`): 2~3단계에서 next 배정·핸드오버를 생략하고
`REQUESTED → ASSIGNED → ESCORTING_TO_FINAL`, A에 `ESCORT_TO_FINAL` 1건만 발행.

---

## 10. 예외 매핑 요약

| 상황 | 감지 채널 | Mission 전이 | FMS 처리 |
|---|---|---|---|
| **FMS 무응답** ★최우선 | Interaction 로컬 타임아웃(5초) | mission 미생성/미진행 | 없음. 지연 도착 task는 로봇이 `REJECT` |
| 사용자 취소 | IF-01 CANCEL | 진행 중 → `CANCELLED` | `cancel_task_id` + `RETURN_TO_BASE` |
| 비상정지 | IF-02 `state=EMERGENCY` | 진행 중 → `EMERGENCY` | 타 로봇 복귀, 비상 로그, 관제 알림 |
| 통신 장애 | IF-02 미수신 > **10초** | 진행 중 → `FAILED` | 해당 로봇 `ERROR` 표기, 장애 로그 |
| task 실패 | IF-02 `task_status=FAILED` | 진행 중 → `FAILED` | `RETURN_TO_BASE`, 실패 사유 기록 |
| task 거절 | task_ack `REJECT` | 진행 중 → `FAILED` | (재배정 없음 — 시연 전제) 로그 |
| 목적지 해석 실패 | **Interaction 내부 처리** | — | FMS 도달하지 않음 |
| 배정 실패(가용 로봇 없음) | — | **스코프 아웃**(부록 C) | — |

---

## 부록. 관제 UI용 Flask REST (읽기 전용, GET)

로봇↔FMS의 MQTT와 별개. 인증 없음(시연 LAN 전제), CORS 허용, JSON 응답.

| 엔드포인트 | 응답 |
|---|---|
| `GET /api/robots` | 로봇별 최신 스냅샷 `[{robot_id, state, pose, battery, current_task_id, last_seen}]` |
| `GET /api/missions?limit=20` | 미션 목록(최신순) + 현재 활성 미션 |
| `GET /api/missions/{id}` | 미션 상세 + 전이 이력 + tasks |
| `GET /api/events?limit=50` | IF-05 이벤트 목록 |
