# 로봇 상태 → 키오스크 UI 연동 계약서 (IF‑02 / ui_state)

> **대상**: 주행(Driving) 트랙 담당자 + 그쪽 Claude Code
> **목적**: 로봇이 자기 상태를 JSON으로 publish하면, 키오스크 UI(`src/alfred_interaction`)가
> 구독해 알맞은 화면으로 전환합니다. 이 문서대로 publish만 하면 끝 — **UI 쪽은 이미 구현·검증 완료**입니다.

---

## 0. TL;DR (이것만 지키면 됨)

- **토픽**: `/robot2/ui_state`(1층) · `/robot4/ui_state`(2층)
- **타입**: `std_msgs/String`, `data`에 **JSON 문자열**
- **필수 필드**: `state` 하나. 나머지는 화면을 풍부하게 하는 선택 필드.
- 상태가 **바뀔 때만** publish(on‑change). 시작 시 publisher는 미리 생성해 둘 것(아래 §10 주의).

```bash
ros2 topic pub /robot2/ui_state std_msgs/msg/String \
  "{data: '{\"state\":\"ESCORT_1F\",\"robot_id\":\"robot2\",\"destination\":{\"poi_id\":\"WC\"},\"progress\":0.4}'}"
```

---

## 1. 토폴로지 / 방향

```
[로봇/주행 노드] --publish--> /robotN/ui_state --(rosbridge 9090, 단일 허브)--> [UI 노트북(브라우저)]
                                                                              구독 → 화면 전환
```

- **방향**: 로봇 → UI (inbound). 한 방향입니다.
- UI → 로봇(IF‑01: INTERACTING/ESCORT/CANCEL)은 **`/information`** 으로 별개입니다. 이 계약과 무관.
- rosbridge는 **두 터틀봇과 연결된 단일 허브 노트북**에서 1개만 돕니다(9090). 두 UI 노트북이 각자 자기 로봇 토픽을 구독합니다.

---

## 2. 토픽 (per‑robot)

| 층 | 로봇 | UI가 구독하는 토픽 |
|---|---|---|
| 1층 | robot2 | `/robot2/ui_state` |
| 2층 | robot4 | `/robot4/ui_state` |

- 1층 UI는 `/robot2/ui_state`만, 2층 UI는 `/robot4/ui_state`만 받습니다. → **각 로봇은 자기 토픽에만** 자기 상태를 publish.
- UI는 빌드 층(`VITE_FLOOR`)에서 토픽을 자동 생성합니다. (필요 시 `.env`의 `VITE_ROBOT_STATE_TOPIC`로 override)

---

## 3. 메시지 형식

**권장**: `std_msgs/String`, `data` = 아래 JSON 객체를 문자열화(`json.dumps`).

UI 파서는 **관대**합니다. 아래 형태 전부 처리합니다(편한 걸로):
| 보내는 형태 | 예시 |
|---|---|
| `std_msgs/String` + JSON | `{ data: '{"state":"ESCORT_1F","destination":{"poi_id":"WC"}}' }` |
| `std_msgs/String` + 라벨만 | `{ data: "DOCKING" }` |
| 커스텀 msg(필드 직접) | `{ state:"ESCORT_1F", destination:{...}, battery:73 }` |
| 맨 문자열 | `"PATROL"` |

- 키는 **snake_case**(`robot_id`, `poi_id`, `target_floor`) 권장 — camelCase도 인식합니다.
- `state`를 못 찾으면 메시지는 **무시**됩니다(에러 아님).

---

## 4. JSON 스키마

| 필드 | 타입 | 필수도 | 의미 / 언제 |
|---|---|---|---|
| `state` | string | ✅ **필수** | 상태 문자열(§5의 값 중 하나). 화면을 결정. |
| `robot_id` | string | 권장 | `"robot2"` \| `"robot4"`. 로깅·검증용. |
| `destination` | `{ poi_id?, name? }` | ESCORT_* 시 | 안내 목적지. `poi_id`(§6)만 주면 UI가 다국어 이름 자동 조회. `name`은 직접 표시명. |
| `target_floor` | number `1`\|`2` | …_FINISHED 시 | 사용자가 이동할 층. 없으면 UI가 "반대 층"으로 자동 가정. |
| `battery` | number `0~100` | DOCKING/UNDOCKING 시 | 충전 화면에 "충전 … · NN%". |
| `progress` | number `0~1` | ESCORT_* 시 | 안내 진행바. |
| `timestamp` | string(ISO8601) | 선택 | 디버그/신선도(현재 화면엔 미표시). |

---

## 5. `state` 값 — 전체 목록과 UI 효과

| `state` | 의미 | UI 화면 | 함께 보내면 좋은 필드 |
|---|---|---|---|
| `PATROL` | 순찰 | 순찰(웃는 얼굴)로 복귀 | — |
| `ESCORT_1F` | robot2가 1층에서 시설 안내중 | 안내중 화면 "○○로 안내중" + 진행바 | `destination.poi_id`, `progress` |
| `ESCORT_2F` | robot4가 2층에서 시설 안내중 | 〃 | `destination.poi_id`, `progress` |
| `WAITING_1F` | robot2가 1층에서 사용자 대기 | 대기 화면 "잠시만 기다려 주세요" | — |
| `WAITING_2F` | robot4가 2층에서 사용자 대기 | 〃 | — |
| `GO_HANDOVER` | robot4가 2층 핸드오버(픽업) 지점으로 **이동 중** (WAITING_2F 직전) | 대기 화면 "안내를 준비하고 있어요 · 곧 모시러 갈게요" | — |
| `ESCORT_1F_FINISHED` | 1층 안내 완료(→ 다음 층) | 대기 화면 "○○ F로 이동해 주세요" | `target_floor`(없으면 2 가정) |
| `ESCORT_2F_FINISHED` | 2층 안내 완료(→ 다음 층) | 〃 | `target_floor`(없으면 1 가정) |
| `ESCORT_COMPLETED` | 시설 안내 최종 완료 | 순찰로 복귀 | — |
| `DOCKING` | 도킹/충전 중 | 충전 화면 "충전 중 · NN%" | `battery` |
| `UNDOCKING` | 언도킹(충전 끝) | 충전 화면(잠깐) → 곧 `PATROL` 보낼 것 | `battery` |
| `FIRE` / `INJURED` / `SUSPICIOUS` | 비상 감지 | 전체화면 경보 | **§9 참고 — `/detection` 권장** |

> 각 UI는 자기 층 변형만 받습니다(1층 UI엔 `_1F`, 2층 UI엔 `_2F`). 같은 로봇 토픽에 다른 층 변형을 섞어 보내지 마세요.

---

## 6. `destination.poi_id` 유효값 (UI 시설 테이블과 일치해야 함)

ESCORT에서 목적지 이름을 띄우려면 **아래 `poi_id` 중 하나**를 보내세요(UI가 다국어 이름으로 변환). 매칭 안 되면 일반 "시설 안내중"으로만 표시됩니다.

**1층 (robot2)**
| poi_id | 이름 |
|---|---|
| `entrance` | 1번 출구 |
| `entrance2` | 2번 출구 |
| `info` | 안내데스크 |
| `lift` | 엘리베이터 |
| `WC` | 화장실 |
| `esc` | 에스컬레이터 |

**2층 (robot4)**
| poi_id | 이름 |
|---|---|
| `pl_1` / `pl_2` / `pl_3` | 탑승구 A‑1 / A‑2 / A‑3 |
| `trans` | 환승출구 |
| `gate` | 개찰구 |
| `gate_b` | 개찰구(장애인용) |
| `lift2` | 엘리베이터 |
| `esc2` | 에스컬레이터 |

> 원본: `src/alfred_interaction/src/config/facilities.ts`. 값이 바뀌면 이 표도 같이 갱신.

---

## 7. 예시 (그대로 복붙 테스트 가능)

```bash
# 순찰
ros2 topic pub /robot2/ui_state std_msgs/msg/String "{data: '{\"state\":\"PATROL\",\"robot_id\":\"robot2\"}'}"

# 안내중(화장실, 40%)
ros2 topic pub /robot2/ui_state std_msgs/msg/String \
  "{data: '{\"state\":\"ESCORT_1F\",\"robot_id\":\"robot2\",\"destination\":{\"poi_id\":\"WC\"},\"progress\":0.4}'}"

# 1층 안내 완료 → 2층으로 이동 안내
ros2 topic pub /robot2/ui_state std_msgs/msg/String \
  "{data: '{\"state\":\"ESCORT_1F_FINISHED\",\"robot_id\":\"robot2\",\"target_floor\":2}'}"

# 대기
ros2 topic pub /robot4/ui_state std_msgs/msg/String "{data: '{\"state\":\"WAITING_2F\",\"robot_id\":\"robot4\"}'}"

# 충전(73%)
ros2 topic pub /robot2/ui_state std_msgs/msg/String "{data: '{\"state\":\"DOCKING\",\"robot_id\":\"robot2\",\"battery\":73}'}"

# 최종 완료 → 순찰 복귀
ros2 topic pub /robot2/ui_state std_msgs/msg/String "{data: '{\"state\":\"ESCORT_COMPLETED\",\"robot_id\":\"robot2\"}'}"
```

> `-r 1`(반복) 대신 `--once` 또는 노드에서 상태 변경 시 1회 발행 권장.

---

## 8. 핸드오프 시나리오 (1층 → 2층, 예시 순서)

사용자가 1층에서 2층 목적지를 요청한 경우(robot2가 1층 안내 → robot4가 2층 이어받음):

| 시점 | `/robot2/ui_state` (1층 UI) | `/robot4/ui_state` (2층 UI) |
|---|---|---|
| 1F 안내 시작 | `ESCORT_1F` (+destination, progress) | — |
| 1F 환승점 도착 | `ESCORT_1F_FINISHED` (+`target_floor:2`) | `WAITING_2F` |
| 사용자 2F 도착, 이어 안내 | `PATROL`(또는 복귀) | `ESCORT_2F` (+destination, progress) |
| 목적지 도착 | — | `ESCORT_COMPLETED` |

> 각 로봇은 **자기 토픽에 자기 상태만** 보냅니다. UI는 자기 층 흐름만 보면 됩니다.

---

## 9. 경계 — 비상(FIRE/INJURED/SUSPICIOUS)은 `/detection`

비상 감지는 **이미 `/detection` 채널로 구현·연결**되어 있습니다(문서: `경보모듈_가이드.md`).
- **권장**: 비상은 `/detection`으로만 보내고 `ui_state`엔 넣지 마세요(이중 경보 방지).
- 참고: `ui_state`에 `FIRE` 등을 보내도 UI가 경보로 처리하긴 합니다. 단 **한 채널만** 쓰세요.

---

## 10. 로봇 쪽 구현 힌트 (Claude Code용)

작은 publisher 노드 하나면 됩니다. 핵심:
- `std_msgs/String` publisher를 **노드 시작 시 생성**(미리 만들어 둬야 rosbridge가 타입을 알 수 있음 — §주의).
- 내부 상태가 바뀔 때만 `data = json.dumps({...})`로 publish(on‑change). 같은 상태 반복 발행 불필요.

```python
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

ROBOT_ID = "robot2"                       # 1층=robot2 / 2층=robot4
TOPIC = f"/{ROBOT_ID}/ui_state"

class UiStatePublisher(Node):
    def __init__(self):
        super().__init__("ui_state_publisher")
        self.pub = self.create_publisher(String, TOPIC, 10)   # 시작 시 생성(중요)
        self._last = None

    def publish_state(self, state: str, **fields):
        payload = {"state": state, "robot_id": ROBOT_ID, **fields}
        key = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if key == self._last:
            return                                            # on-change만
        self._last = key
        self.pub.publish(String(data=json.dumps(payload, ensure_ascii=False)))

# 사용 예
# self.publish_state("ESCORT_1F", destination={"poi_id": "WC"}, progress=0.4)
# self.publish_state("ESCORT_1F_FINISHED", target_floor=2)
# self.publish_state("DOCKING", battery=73)
# self.publish_state("PATROL")
```

**기존 코드와의 관계**: `alfred_bridge`의 `escort_state_bridge_node`(`/escort_state`)와 `RobotState.msg`는
`IDLE/TO_TRANSFER/ESCORTING/...` 등 **다른 vocabulary**(FMS/모니터 공용)입니다. 이 `ui_state`는 **UI 전용**이라
충돌하지 않습니다. 기존 상태머신에서 UI 문자열로 매핑해 별도 토픽에 publish하면 됩니다.

> ⚠️ **시작 순서 주의**: UI는 구독 시 타입을 명시하지 않습니다. 따라서 **로봇 publisher가 먼저 떠 있어야**
> rosbridge가 `/robotN/ui_state`의 타입(`std_msgs/String`)을 추론합니다. 노드 시작 시 `create_publisher`를
> 호출해 두면(메시지를 아직 안 보냈어도) 해결됩니다. (UI를 "타입 명시 구독"으로 바꿔 순서 무관하게 만들 수도
> 있으니 필요하면 UI 담당에게 요청하세요.)

---

## 11. 테스트

**UI만(로봇 없이)** — 브라우저 콘솔(F12):
```js
window.alfredRobotStatus('DOCKING')
window.alfredRobotStatus({ state:'ESCORT_1F', destination:{ poi_id:'WC' }, progress:0.5 })
window.alfredRobotStatus({ state:'ESCORT_1F_FINISHED', target_floor:2 })
window.alfredRobotStatus('PATROL')
```

**실제 경로** — 허브 노트북에서 `ros2 topic pub …`(§7) → 해당 층 키오스크 화면이 바뀌면 정상.
`ros2 topic list`에 `/robot2/ui_state`가 보여야 rosbridge가 중계합니다.

---

## 12. UI가 현재 소비하는 필드 (구현 상태)

| 필드 | UI 반영 |
|---|---|
| `state` | ✅ 화면 전환 |
| `destination.poi_id` / `name` | ✅ 안내중 자막 "○○로 안내중" |
| `target_floor` | ✅ 이동 안내 "N F로" |
| `battery` | ✅ 충전 % |
| `progress` | ✅ 진행바 |
| `robot_id` / `timestamp` | ⛔ 현재 화면 미표시(로깅/검증용) |

---

## 13. UI 쪽 연결 지점 (참고 — 바꿀 일 있으면 여기)

| 무엇 | 파일 |
|---|---|
| 토픽 설정 | `src/config/env.ts`(`VITE_ROBOT_STATE_TOPIC`) · 자동유도는 `src/services/createServices.ts` |
| JSON 파싱 | `src/services/robot-state/RosBridgeRobotStateService.ts`(`parseRobotStatus`) |
| 상태 → 화면 매핑 | `src/core/kiosk/robotStatus.ts`(`robotStatusToEvent`) + `src/features/robot-state/RobotStateProvider.tsx`(ESCORT 처리) |
| 화면 | `features/charging` · `features/waiting` · `features/guiding` |
| poi_id ↔ 이름 | `src/config/facilities.ts` |
