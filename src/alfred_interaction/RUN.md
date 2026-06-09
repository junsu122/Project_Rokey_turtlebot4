# ALFRED 실행 가이드 (1층 / 2층)

> 이 패키지는 **Node 프로젝트**입니다(파이썬 아님). 그래서 `pip install`이 아니라 **`npm install`** 한 번이면
> 필요한 게 전부 깔립니다. 구성은 **UI(브라우저) + 백엔드 프록시(키 보관)** 두 개를 함께 띄우는 형태이고,
> 노트북마다 자기 층 UI와 자기 프록시를 돌립니다.

---

## 1. 설치 (환경 준비)

필요한 것:
- **Node.js 18+** (권장 20 이상) + npm — <https://nodejs.org>
- **Google Chrome** (키오스크 전체화면용)

```powershell
cd C:\Rokey_turtlebot\user_interface
npm install
```

`npm install` 로 함께 설치되는 것(개별 설치 불필요, `package.json`에 모두 명시):

| 영역 | 패키지 |
|------|--------|
| UI | `react`, `react-dom`, `vite` |
| STT(브라우저) | `@soniox/speech-to-text-web` |
| 프록시(서버) | `express`, `cors`, `dotenv`, `@anthropic-ai/sdk`, `zod` |

---

## 2. `.env` 설정 (키 입력)

`.env`는 **git에 올라가지 않습니다.** `.env.example`을 복사해 키 2개만 넣으면 됩니다.

```powershell
Copy-Item .env.example .env
# 그런 다음 .env 에서 ANTHROPIC_API_KEY / SONIOX_API_KEY 두 줄을 본인 값으로 교체
```

| 변수 | 위치 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 서버 전용 | Claude Haiku 4.5 (프록시가 사용) |
| `SONIOX_API_KEY` | 서버 전용 | Soniox 영구 키 (프록시가 임시 키 발급) |
| `VITE_FLOOR` | UI | `1` 또는 `2` — 이 노트북이 맡는 층 |
| `VITE_DEFAULT_LANG` | UI | 기본 언어 `ko`·`en`·`ja`·`zh` |
| `VITE_API_BASE` | UI | 프록시 베이스(기본 `/api`) |
| `VITE_SONIOX_MODEL` | UI | Soniox 모델(기본 `stt-rt-v4`) |
| `VITE_USE_MOCKS` | UI | `true` 면 키 없이 목 STT/LLM (오프라인) |

> 키는 같은 계정이므로 **1층·2층 노트북의 `.env`는 동일**합니다. 층 구분은 키가 아니라 **실행 명령**으로 합니다(아래).

---

## 3. 실행 — 개발 모드 (가장 간단, 권장)

**터미널 2개**가 필요합니다. 프록시는 켠 채로 둡니다.

### 🟦 1층 노트북
```powershell
# 터미널 A — 백엔드 프록시 (계속 켜두기)
cd C:\Rokey_turtlebot\user_interface
npm run server          # http://localhost:8787

# 터미널 B — UI (1층)
cd C:\Rokey_turtlebot\user_interface
npm run dev             # http://localhost:5173
```

### 🟩 2층 노트북
```powershell
npm run server          # 터미널 A (동일)
npm run dev:2f          # 터미널 B  ← 2층(robot4)
```

확인:
```powershell
curl http://localhost:8787/api/health     # soniox:true, anthropic:true 면 정상
```
화면 좌상단 **1F / 2F 배지**로 어느 층 UI인지 바로 확인됩니다.

---

## 4. 실행 — 키오스크 전체화면

```powershell
npm run build           # 1층 빌드  (2층: npm run build:2f)
npm run server          # 프록시
npm run kiosk           # 미리보기 서버 http://localhost:4173
kiosk.bat http://localhost:4173   # Chrome 전체화면(탭/주소창/작업표시줄 없음)
```
개발 모드(3번)로 띄운 상태라면 그냥 `kiosk.bat` 만 더블클릭해도 됩니다(기본 5173 대상). 종료는 Chrome 창에서 **Alt + F4**.

---

## 5. 1층 vs 2층 한눈에

| | 개발 | 빌드 | robot_id | floor | 좌표 출처 |
|---|------|------|----------|-------|----------|
| **1층** | `npm run dev` | `npm run build` | `robot2` | F1 | `VITE_FLOOR=1`(기본) |
| **2층** | `npm run dev:2f` | `npm run build:2f` | `robot4` | F2 | `.env.f2`(`VITE_FLOOR=2`) |

프록시(`npm run server`)는 양쪽 동일합니다.

---

## 6. 오프라인(키 없이) 데모

`.env` 에서 `VITE_USE_MOCKS=true` → 프록시 없이 **목 STT/LLM** 으로 전체 흐름이 동작합니다(데모/개발용).

---

## 6.5 시각장애인 모드 (wake word + TTS)

patrol 화면에서 **"Hello Alfred" / "헬로 알프레드"** 라고 말하면(또는 화면 하단의 음성안내 버튼 탭) **시각장애인 모드**로 진입합니다.

- 즉시 **음성안내(눌러서 말하기가 눌린 상태)** 로 이동, 말이 끝나면 자동 인식(무음 감지) → 핸즈프리.
- 이 모드에서는 **모든 단계에 TTS**(음성)가 나옵니다. 일반 모드는 지금처럼 **무음**.
- 시설 요청이면 확인 멘트 후 자동으로 안내 시작, 목적지 도착하면 **patrol + 일반(general) 모드로 복귀**.
- 서버로 보내는 IF-01의 `customer.profile`이 이 모드에서는 **`VISUALLY_IMPAIRED`** 로 전송됩니다.

> wake word는 브라우저 **Web Speech 음성인식**(무료)으로 감지합니다. **Chrome + 네트워크 + 마이크 권한**이 필요하며(크롬 구현이 클라우드 사용), 미지원/거부 시 patrol 하단의 **버튼**으로 동일하게 진입할 수 있습니다. TTS는 브라우저 `speechSynthesis`(키 불필요).

## 6.6 ros_bridge 연동 (터틀봇4 노트북과 JSON 통신)

IF-01 요청(고객 안내/취소/상호작용)은 **rosbridge 프로토콜 JSON** 으로 터틀봇4가
연결된 노트북에 보냅니다. 와이어 포맷은 그대로 rosbridge `publish` 프레임입니다:

```json
{ "op": "publish", "topic": "/information",
  "msg": { "msg_id": "...", "version": "2.0", "request_id": "REQ_0012",
           "robot_id": "robot2", "request_type": "ESCORT",
           "destination": { "poi_id": "GATE_30", "floor": 2 },
           "origin": { "floor": 1, "pose": { "x": 0.0, "y": 0.0 } },
           "customer": { "customer_id": "C_xxx", "profile": "ELDERLY", "language": "ko" },
           "timestamp": "..." } }
```

- `request_type` 값: **ESCORT**(목적지 확정) · **CANCEL**(취소) · **INTERACTING**(아래).
- **patrol(파란 스마일) → 상호작용** 진입(터치 또는 "헬로 알프레드" 웨이크워드) 순간,
  같은 포맷에 `request_type: "INTERACTING"` 으로 한 번 보냅니다(목적지는 아직 없으므로
  `destination` 생략, `robot_id`/`origin`/`customer` 포함). FMS가 "이 로봇이 응대 시작"을
  미리 알 수 있게 하는 신호입니다.

**연결 방법** — 터틀봇4 노트북에서 rosbridge 실행:
```bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml   # 기본 포트 9090
```
그다음 키오스크 `.env`에 그 노트북 **IP만** 넣고 UI를 다시 띄웁니다 (IP가 바뀌면 이 한 줄만 수정):
```powershell
# .env  ─ IP가 자주 바뀌면 HOST 한 줄만 고치면 전체 반영
VITE_ROSBRIDGE_HOST=192.168.0.42            # 터틀봇4 노트북 IP (포트는 아래)
VITE_ROSBRIDGE_PORT=9090                    # 기본 9090
VITE_ROS_INFO_TOPIC=/information            # 기본값
VITE_ROS_INFO_MSG_TYPE=std_msgs/String      # 기본값(JSON을 .data에 적재). 커스텀 msg면 그 타입
# (고급) 전체 URL을 직접 주려면 VITE_ROSBRIDGE_URL=... (설정 시 HOST/PORT보다 우선)
```

- `VITE_ROSBRIDGE_HOST` 가 **비어 있으면** mock FMS로 동작 — 위 JSON 프레임을 **브라우저
  콘솔**(`[MockFMS] IF-01 … → /information`)에만 출력하므로 로봇 없이도 포맷을 확인할 수 있습니다.
- 클라이언트(`src/services/ros/RosBridgeClient.ts`)는 **자동 재연결 + 오프라인 큐**가 있어,
  링크가 잠깐 끊겨도 보낸 요청을 버퍼링했다가 재연결 시 흘려보냅니다.
- 마이크 때문에 UI는 `localhost`로 열어야 하지만, ros_bridge URL은 **LAN IP** 사용이 정상입니다
  (WebSocket은 마이크 보안 제약과 무관).

## 7. 트러블슈팅

| 증상 | 원인 / 해결 |
|------|-------------|
| `curl http://localhost:8787/...` 연결 안 됨 | **프록시가 안 켜짐.** `npm run server` 를 먼저 띄우고 켜둘 것 |
| 마이크가 안 잡힘 | 반드시 **`localhost`** 로 열 것. LAN IP(`192.168.x`)는 브라우저 보안상 마이크 불가 |
| 음성이 안 끝남 | 말이 끝나면 화면의 **"말하기 끝"** 버튼을 눌러 확정 (Soniox 실시간 특성) |
| 목적지가 서버로 안 가는 듯 | IF-01은 현재 **Mock**이라 브라우저 콘솔에 `[MockFMS] IF-01 …` 로 찍힘(정상). 실제 FMS 전송은 별도 단계 |
| PowerShell로 LLM 직접 호출 시 한글 깨짐 | PowerShell 인코딩 문제. **UI에서 음성으로** 테스트하면 정상(브라우저는 UTF-8) |
| `[soniox]`/`[llm]` 에러 로그 | 프록시 터미널 로그 확인 — 키 오타 / 만료 / 네트워크 점검 |
| `[ros-bridge] link down; retrying…` 반복 | rosbridge 미실행 / IP·포트 오타 / 방화벽. 터틀봇4 노트북에서 `rosbridge_websocket`(9090) 실행 확인, `.env`의 `VITE_ROSBRIDGE_HOST` 점검 |
| IF-01이 로봇에 안 도착 | rosbridge가 타입을 몰라 publisher를 못 만들 수 있음 → `VITE_ROS_INFO_MSG_TYPE` 에 토픽 메시지 타입 지정 |

---

## 참고
- 한·영·일·중 4개 언어: 화면 우상단 **언어 선택**으로 전환(STT·LLM 응답 모두 해당 언어).
- 층간 **얼굴 인계 CV(요구 1.5.1)** 는 모델 조사 후 **다음 단계**로 분리되어 있습니다.
- 더 자세한 아키텍처/서비스 교체 방법은 [`README.md`](./README.md) 참고.
