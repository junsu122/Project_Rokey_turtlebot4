# ALFRED 키오스크 UI — 코드 구조 정리 (Interaction 파트)

> 대상: `src/alfred_interaction` (React + TypeScript + Vite UI) + `server`(키 보관 프록시)
> 함께 보기: 화면 전환은 `시나리오_정리.md` / `flowchart.drawio`, 핵심 파일 해설은 `핵심코드_설명.md`

---

## 0. 한눈 요약

- **규모**: `src/` 102개 `.ts/.tsx` · 약 6,554 LOC · CSS 모듈 19개
- **설계 원칙**: **"화면은 상태머신이, 데이터는 서비스가"** — 순수 리듀서 하나가 화면을 결정하고, 모든 입출력(STT/LLM/TTS/ROS)은 서비스 레이어로 격리되어 **목(mock)↔실물 교체**가 가능
- **스택**: React 18 · TypeScript · Vite. 백엔드는 API 키를 브라우저에서 숨기기 위한 Express 프록시 하나뿐 — **별도 FMS 관제 서버 없음**, 외부 연동은 rosbridge 서버(허브 노트북 9090) 하나로 수렴

## 1. 전체 디렉터리 트리

```
src/
├─ main.tsx               # 엔트리: React 마운트
├─ app/        (4)        # 합성 루트 + 셸 + 라우터 + 오버레이
├─ core/       (25)       # 프레임워크 무관 도메인·상태·유틸  ← §3 상세
├─ config/     (6)        # 빌드타임 설정 + 정적 데이터       ← §4 상세
├─ services/   (37)       # IO/DI 레이어 (목·실물 8종)        ← §5
├─ features/   (19)       # 화면 + 전용 Provider               ← §6
├─ components/ (8)        # 공유 프레젠테이션 컴포넌트          ← §7
└─ styles/                # 전역 스타일
server/
└─ proxy.mjs              # Express 백엔드(키 보관, 3 엔드포인트)  ← §8
```

## 2. 진입 · 조립 (`src/app/`)

| 파일 | 담당 |
|---|---|
| `main.tsx` | React 루트 마운트 (`<App/>`) |
| `App.tsx` | **합성 루트.** Provider 중첩 순서 = 의존 방향: `Language → Service → Kiosk(상태머신) → Guidance → Alerts → RobotState → KioskApp` |
| `KioskApp.tsx` | **셸.** 키오스크 하드닝(`useKioskMode`), 클릭음(`useUiSounds`), 유휴 타이머(`useIdleTimer`, 홈/지도/음성에서만) + `KioskRouter`·`StaffCallOverlay` 렌더 |
| `KioskRouter.tsx` | `screen` 값 → 화면 8종 중 1개 마운트 (**화면이 마운트되는 유일한 곳**) |
| `StaffCallOverlay.tsx` | 직원 호출 팝업(화면과 직교하는 오버레이) |

---

## 3. `core/` — 도메인 · 상태 · 유틸 (파일 단위)

프레임워크/화면과 무관한 "두뇌". 6개 하위 모듈.

### 3.1 `core/kiosk/` (6) — 상태머신 (앱의 심장)

| 파일 | 담당 |
|---|---|
| `kioskMachine.ts` | **순수 리듀서 `kioskReducer` + `initialKioskState`.** 18종 이벤트를 화면 전환으로 처리하는 단일 진실원. 안전 가드(유휴가 안내중을 안 끊음 · 경보 중 로봇 화면 차단 · PATROL이 로컬 안내·도착 화면을 안 끊고 남은 경보는 해제) |
| `types.ts` | 상태머신 **어휘 사전.** `KioskState`, `KioskEvent`(18종 유니온), `KioskScreen`(8종), `RobotEscortInfo`(destinationName/ratio/preparing/arrived), `WaitingInfo`, `KioskMode`(general/VI) |
| `robotStatus.ts` | **IF-02 → 이벤트 매핑.** 로봇 상태 문자열 13종(`RobotStatus`)을 `robotStatusToEvent()`로 번역. `RobotStatusMessage`(정규화된 수신 형태) 정의. ESCORT_1F/2F만 null 반환(목적지명 해석은 Provider가) |
| `KioskProvider.tsx` | `useReducer(kioskReducer)`로 State/Dispatch 두 context 제공 |
| `useKiosk.ts` | `useKioskState()` / `useKioskDispatch()` 접근 훅 (context 미사용 시 throw) |
| `index.ts` | 배럴 |

### 3.2 `core/domain/` (5) — 순수 도메인 타입 (UI·프레임워크 없음)

| 파일 | 담당 |
|---|---|
| `facility.ts` | `Facility` 타입(이름/다국어/카테고리/층/poiId/pose/도면좌표/별칭) + `FacilityCategory`(14종). 헬퍼: `isSelectableFacility()`(poiId 있고 숨김 아님), `isTransferFacility()`, `localizedFacilityName()`(언어별 이름, 한국어 폴백) |
| `navigation.ts` | 에스코트 도메인. `NavigationPlan`(same/cross-floor + `TransferStep` 환승), `NavigationSession`(live 세션), `NavigationProgress`/`NavigationPhase`(starting→moving→awaiting-handoff→arrived/cancelled/error), `isTerminalPhase()` |
| `floor.ts` | `Floor`(이름/shortName/level/도면) + 도면 요소 `BlueprintRoom`/`BlueprintWall`/`BlueprintDecoration` 타입 |
| `detection.ts` | 비상 `DetectionType`(FIRE/INJURED/SUSPICIOUS) + 별칭표(`화재/injured/거동수상…`) + `parseDetectionLabel()`(대소문자·부분일치 관대 파서 — `INJURED_PERSON`→INJURED 등) |
| `index.ts` | 배럴 |

### 3.3 `core/i18n/` (3) — 언어 상태 (번역 카탈로그는 config에)

| 파일 | 담당 |
|---|---|
| `language.ts` | `Language`(ko/en/ja/zh), `AppStrings` 인터페이스(모든 UI 문자열 형태), `LANGUAGES`/`DEFAULT_LANGUAGE`/`isLanguage()` |
| `LanguageProvider.tsx` | 활성 언어 state + context, `useLanguage()` 훅 |
| `index.ts` | 배럴 |

### 3.4 `core/hooks/` (6) — 횡단 React 훅

| 파일 | 담당 |
|---|---|
| `useIdleTimer.ts` | 무입력 N초 → `onIdle` 콜백 (홈/지도/음성에서만 활성). 활동 이벤트(pointer/key/touch/mouse/wheel) 리스닝, 안내중 보호의 방어선 |
| `useKioskMode.ts` | 키오스크 하드닝(#1): 우클릭·제스처 차단, 첫 입력 시 풀스크린 요청, 커서 숨김 |
| `useUiSounds.ts` | 전역 클릭음 — 위임된 `pointerdown` 하나로 모든 `<button>` 커버 + 오디오 컨텍스트 unlock |
| `useAnyInput.ts` | patrol에서 `click`/`keydown`으로 깨우기. ⚠️ `pointerdown`이 아닌 **완료된 `click`**을 듣는 이유 주석(탭이 홈 버튼으로 새는 것 방지) |
| `useWakeWord.ts` | Web Speech API(무료, 키 없음)로 웨이크워드("헬로 알프레드") 감지 → VI 음성 플로우 진입. 유료 Soniox와 분리(유휴 중 과금 방지) |
| `index.ts` | 배럴 |

### 3.5 `core/audio/` (2) — 음향 (음원 파일 없음)

| 파일 | 담당 |
|---|---|
| `sfx.ts` | Web Audio 합성. `playClick()`(버튼 블립), `playBeep()`(VI 위치 비프), `playSiren('fire'\|'police')`(주파수 스윕 사이렌, stop 반환), `unlockAudio()`. 단일 지연 생성 AudioContext |
| `index.ts` | 배럴 |

### 3.6 `core/utils/` (3) — 의존성 없는 유틸

| 파일 | 담당 |
|---|---|
| `cx.ts` | `cx(...)` — truthy 클래스명 join |
| `id.ts` | `makeId(prefix)` — 카운터+랜덤 유니크 ID(세션/플랜/IF-01 request_id) |
| `index.ts` | 배럴 |

---

## 4. `config/` — 빌드타임 설정 + 정적 데이터 (파일 단위)

| 파일 | 담당 |
|---|---|
| `env.ts` | **빌드타임 설정 단일 출처.** `VITE_*`를 파싱해 `env` 객체 생성: `useMocks`, `rosbridgeUrl`(HOST+PORT 조립), **`robotDrivesUi`**(=!useMocks&&rosbridge), 토픽(`rosInfoTopic`/`detectionTopics`/`robotStateTopic`), 마이크 게이트, 기본 언어/층 |
| `kiosk.config.ts` | **층별 런타임 설정 `kioskConfig`.** `VITE_FLOOR`로 프로필 결정(1층=robot2/F1, 2층=robot4/F2), `robotId`/`currentFloorId`/`originPose`, 타이머(유휴 60초·시뮬 이동 6초·도착 유지 2.6초), 풀스크린/커서 |
| `facilities.ts` | **POI 테이블 `facilities[]`** — 1층 6개 + 2층 11개. 각 시설: 4개국어 이름·`poiId`(FMS 전송용)·`pose`(로봇 맵 좌표 m)·`position/footprint`(도면 좌표)·`aliases`(음성/LLM 매칭). 벤치는 `selectable:false`(표시 전용) |
| `floors.ts` | **`floors[]` + `BLUEPRINT` 좌표계.** 층 외곽선·벽(개찰구 틈)·장식(열차). 실제 시설은 facilities의 footprint로 그림 |
| `i18n.ts` | **번역 카탈로그 `messages`**(ko/en/ja/zh 전체 UI 문자열) + `useStrings()`(활성 언어 카탈로그 반환) |
| `index.ts` | **배럴 + 조회 헬퍼**(features가 raw 배열을 직접 인덱싱 안 하도록): `getFloor`/`floorLevel`(F1→1), `getFacility`/`getFacilityByPoiId`(WC→화장실), `facilitiesOnFloor`, **`transferPointsOnFloor`**(엘베→에스컬 순, 환승 #6용), `otherFloorId` |

> **config vs core 경계**: `core/domain`은 *타입과 규칙*(Facility가 무엇인가), `config`는 *실제 데이터*(우리 역의 시설 목록·층·번역)와 *빌드 설정*. 헬퍼(`getFacilityByPoiId` 등)는 데이터를 다루므로 config에 둔다.

---

## 5. `services/` — IO/DI 레이어 (목↔실물 8종)

`createServices.ts`가 `.env`를 보고 목/실물을 고르는 **유일한 곳**. 화면 코드는 목/실물을 모름.

| 서비스 | 인터페이스 | 실물 구현 | 채널/비고 |
|---|---|---|---|
| `stt` | SttService | `SonioxSttService` | 프록시로 임시키 발급 |
| `llm` | LlmService | `ClaudeLlmService` | 프록시 `/api/llm/understand` |
| `tts` | TtsService | `WebSpeechTtsService` | 브라우저 내장(키 없음) |
| `fms` | FmsService | `RosBridgeFmsService` | **IF-01 송신** → `/information` (+`if01.ts` 와이어 빌더) |
| `detection` | DetectionService | `RosBridgeDetectionService` | **수신** ← `/robotN/detection/info` |
| `robotState` | RobotStateService | `RosBridgeRobotStateService` | **수신** ← `/robotN/ui_state` |
| `navigation` | NavigationService | (항상 `MockNavigationService`) | 오프라인 에스코트 시뮬만 |
| `ros` | RosService | (항상 `MockRosService`) | 내부 goal — 실가동 미사용 |

- `ros/RosBridgeClient.ts` — rosbridge v2 wire 프로토콜 직접 구현(자동 재연결·큐잉·재구독). FMS·detection·robotState가 **소켓 하나 공유**.
- `services/types.ts`(Services 인터페이스) · `ServiceProvider.tsx`(context) · `index.ts`(배럴) · `useSpeak.ts`(TTS 헬퍼 훅).

## 6. `features/` — 화면 + 브리지 Provider

화면(`*Screen.tsx`)은 표시만, **Provider가 인바운드 데이터 → 상태머신 이벤트**로 번역.

| 폴더 | 화면 | Provider/로직 |
|---|---|---|
| `patrol` | PatrolScreen (웨이크워드·TTS 자기소개) | — |
| `home` | HomeScreen | — |
| `map` | MapScreen + Blueprint(도면 SVG) | — |
| `voice` | VoiceScreen | `useVoiceFlow`(STT→LLM, 침묵 1.5s/상한 12s) |
| `guiding` | GuidingScreen (로컬 vs 로봇 이중 소스·불확정 바·도착 화면) | `GuidanceProvider`(에스코트 오케스트레이터, robotDrivesUi 분기) |
| `waiting` | WaitingScreen ("N층 이동") | — |
| `charging` | ChargingScreen (배터리%) | — |
| `alerts` | AlertScreen + `alerts.config.ts`(이모지/사이렌/문구) | `AlertsProvider`(`/robotN/detection/info` → DETECTION) |
| `robot-state` | — | `RobotStateProvider`(`/robotN/ui_state` → ROBOT_ESCORT/ENTER_*/ROBOT_ARRIVED) |

## 7. `components/` — 공유 프레젠테이션 (8)

`BigButton` · `ButlerFace`(순찰 얼굴) · `RobotFace`(안내중 얼굴) · `FacilityIcon` · `LanguageSwitcher` · `Modal` · `ScreenFrame`(화면 공통 틀) · `StaffCallButton`.

## 8. `server/` + 루트 스크립트

**`server/proxy.mjs`** (Express :8787) — 키를 브라우저에서 격리하는 **유일한 백엔드**:
- `POST /api/llm/understand` — Claude Haiku 4.5(구조화 출력으로 시설/잡담 판정)
- `POST /api/soniox/temporary-api-key` — Soniox 임시키 발급
- `GET /api/health` — 키 설정 점검
- 브라우저 → `/api` → Vite 프록시(`vite.config.ts`) → `:8787`

**`ws-robot-state.mjs`**(루트) — 앱이 아니라 **독립 디버그 CLI**(rosbridge 구독 로그). ⚠️ URL/토픽이 stale(`.81`·`/escort_state`) — 참고용.

## 9. 데이터 흐름 (외부 경계)

```
[브라우저 UI] ──IF-01 /information──────▶ rosbridge:9090 ──▶ web_request_node(주행)
     ▲  ▲                                       │
     │  └──/robotN/ui_state (상태, IF-02)────────┤ escort_state_bridge_node
     │  ◀──/robotN/detection/info (감지)─────────┘ detector_node(비전)
     └──/api (STT 임시키 · LLM)──▶ proxy.mjs:8787 ──▶ Soniox · Anthropic
```

- 1층 키오스크 = `robot2`, 2층 = `robot4` (각 노트북 `VITE_FLOOR`로 결정 — 토픽/robot_id가 그에 맞게 유도)
- 로봇·서버 없이도 콘솔 훅으로 전 화면 시연: `window.alfredRobotStatus(...)`, `window.alfredAlert(...)`
