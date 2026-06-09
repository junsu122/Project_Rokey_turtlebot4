# ALFRED — 지하철 역사 안내 로봇 키오스크 UI

Turtlebot4 위에 올라가는 **터치 키오스크 UI**입니다. 지하철 역사(1층/2층, 층마다 로봇 1대)에서
사용자에게 시설(화장실·역무실·출구 등)을 안내하고, 평소에는 순찰(patrol)하며 웃는 얼굴을 띄웁니다.

> 이 저장소는 **UI(Interaction 트랙)** 를 구현합니다. **STT는 Soniox `stt-rt-v4`, LLM은 Claude
> Haiku 4.5** 가 기본값이며, 키는 **백엔드 프록시(`server/proxy.mjs`)** 가 들고 브라우저는 프록시만
> 호출합니다. ROS 토픽/Nav/멀티층 핸드오프(FMS)는 여전히 **인터페이스 + 목(mock)** 이고, 층간
> **얼굴 인계 CV(요구 1.5.1)** 는 모델 조사 후 다음 단계로 분리되어 있습니다. 오프라인 개발은
> `VITE_USE_MOCKS=true` 로 목 STT/LLM 만으로 전체 흐름이 동작합니다. ("server pluggable" — `src/services`)

---

## 빠른 시작

> 📖 1층/2층 실행 · 설치 · 환경변수 단계별 가이드는 **[`RUN.md`](./RUN.md)** 참고.

```bash
npm install
cp .env.example .env     # ANTHROPIC_API_KEY / SONIOX_API_KEY 입력

npm run server           # 백엔드 프록시 (http://localhost:8787) — 키 보관
npm run dev              # UI 개발 서버 (http://localhost:5173). /api → 프록시로 자동 포워딩

npm run build            # 타입체크 + 프로덕션 빌드 (dist/)
npm run typecheck        # 타입체크만
```

- **2층(robot4) 빌드**: `npm run dev:2f` / `npm run build:2f` (`.env.f2` → `VITE_FLOOR=2`).
- **오프라인(키 없이) 데모**: `.env` 에 `VITE_USE_MOCKS=true` → 프록시 없이 목 STT/LLM 으로 동작.

요구 환경: Node 18+ (개발은 Node 24 / npm 11에서 검증).

### 환경 변수 (`.env`)

| 변수 | 위치 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 서버 전용 | Claude Haiku 4.5 (프록시) |
| `SONIOX_API_KEY` | 서버 전용 | Soniox 영구 키 (프록시가 임시 키 발급) |
| `VITE_FLOOR` | UI | `1` 또는 `2` — 이 Alfred가 맡는 층 |
| `VITE_DEFAULT_LANG` | UI | `ko`·`en`·`ja`·`zh` 기본 언어 |
| `VITE_API_BASE` | UI | 프록시 베이스(기본 `/api`) |
| `VITE_USE_MOCKS` | UI | `true` 면 목 STT/LLM (오프라인) |

---

## 키오스크 모드로 띄우기 (요구사항 #1)

탭/제목/주소(omnibox)/북마크 바와 Windows 작업 표시줄이 **전부 없는** 전체화면은 브라우저를
**실행 시점**에 `--kiosk` 로 띄워서 만듭니다. (웹앱 자체는 컨텍스트 메뉴/제스처 차단 + 첫 터치 시
Fullscreen 요청까지만 담당 — `useKioskMode`.)

### ⭐ 원클릭: `start-kiosk.bat` 더블클릭

빌드 → 미리보기 서버 → Chrome 키오스크까지 한 번에 실행하고, **키오스크 창을 닫으면(Alt+F4)
서버도 자동 정리**됩니다.

```
C:\Rokey_turtlebot\user_interface\start-kiosk.bat   ← 더블클릭
```

- 종료: 키오스크 창에서 **Alt + F4**
- 별도 임시 프로필로 새 Chrome 인스턴스를 띄우므로 평소 쓰던 탭/북마크가 보이지 않습니다.

### 빠른 방법 (개발 중)

- 이미 열린 창에서 **`F11`** → 전체화면(툴바/표시줄 사라짐). 데모용으로 충분.
- 또는 `npm run dev` 를 켠 상태에서 `kiosk.bat` 더블클릭(개발 서버 5173 대상).

### 수동 2단계

```powershell
# 1) 정적 서버 실행
npm run kiosk      # http://localhost:4173

# 2) Chrome을 키오스크로 실행 (※ 기존 Chrome이 떠 있어도 새 인스턴스로 뜨도록 user-data-dir 필수)
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --kiosk "http://localhost:4173" `
  --user-data-dir="$env:TEMP\alfred-kiosk-profile" `
  --start-fullscreen --disable-pinch --overscroll-history-navigation=0 `
  --disable-features=TranslateUI --no-first-run --no-default-browser-check
```

- 작업 표시줄이 계속 보이면 작업 표시줄 설정에서 **자동 숨기기**를 켜세요.
- `Alt+F4` 등 종료키까지 봉인하는 무인 운영은 Windows **할당된 액세스(Assigned Access)** / **Shell Launcher**
  또는 Chrome 엔터프라이즈 정책으로 잠그는 것이 정석입니다.

### 런처 파일

| 파일 | 용도 |
|------|------|
| `start-kiosk.bat` | **원클릭**: 빌드+서버+키오스크, 종료 시 서버 자동 정리 |
| `kiosk.bat` | Chrome 키오스크만 실행 (서버는 따로 띄워둔 상태에서) |

---

## 아키텍처

레이어가 단방향으로 의존하도록 설계했습니다. **UI는 서비스 "인터페이스"에만** 의존하고, 구체 구현
(목/실제)은 한 곳(`createServices`)에서만 선택합니다.

```
src/
├─ app/                 앱 셸: 프로바이더 조립 + 라우터 + 오버레이
│   ├─ App.tsx          ServiceProvider → KioskProvider → GuidanceProvider → KioskApp
│   ├─ KioskApp.tsx     kiosk-mode/idle 타이머, 화면+팝업 렌더
│   ├─ KioskRouter.tsx  상태 → 화면 매핑 (화면이 마운트되는 유일한 곳)
│   └─ StaffCallOverlay.tsx   직원 호출 팝업 (#11)
│
├─ core/                프레임워크/도메인 코어 (UI 비의존)
│   ├─ domain/          Facility / Floor / Navigation 타입 (순수)
│   ├─ kiosk/           유한상태기계: types · kioskMachine(reducer) · Provider · hooks
│   ├─ hooks/           useIdleTimer · useKioskMode · useAnyInput
│   └─ utils/           makeId · cx
│
├─ core/i18n/           Language · LanguageProvider · useStrings (ko/en/ja/zh)
│
├─ services/            ★ 서버 경계 — 인터페이스 + 목/실제 구현
│   ├─ ros/             RosService  + MockRosService                (ROS 토픽/Nav 목표)
│   ├─ stt/             SttService  + Soniox‑/MockSttService         (Soniox stt-rt-v4)
│   ├─ llm/             LlmService  + Claude‑/MockLlmService         (발화 → 의도/시설/응답)
│   ├─ navigation/      NavigationService + MockNavigationService    (경로/멀티층 핸드오프)
│   ├─ fms/             FmsService  + MockFmsService                 (IF-01 고객 요청)
│   ├─ createServices.ts   구성 루트(여기서만 목/실제 선택; STT/LLM 기본=실제)
│   └─ ServiceProvider.tsx DI 컨텍스트 (useServices)
│
├─ features/            화면별 기능
│   ├─ patrol/          순찰 화면
│   ├─ home/            초기 화면, 버튼 A/B + 직원호출 + 층 배지 + 언어 선택
│   ├─ map/             지도(도면) 안내 — Blueprint + 시설 리스트
│   ├─ voice/           음성 안내 — useVoiceFlow (STT→LLM→시설 확인 / 자유 응답)
│   └─ guiding/         안내중 화면 + GuidanceProvider(경로 오케스트레이션)
│
├─ components/          공용 컴포넌트 (CSS Modules)
│   ScreenFrame · BigButton · RobotFace(^^) · Modal · StaffCallButton · FacilityIcon · LanguageSwitcher
│
├─ config/             데이터/설정 (코드와 분리)
│   facilities(poiId·실좌표) · floors · i18n(4개 언어 문구) · env(VITE_*) · kiosk.config
│
└─ styles/             tokens.css(디자인 토큰) · global.css(리셋/키오스크 하드닝)

server/proxy.mjs        백엔드 프록시: Soniox 임시키 발급 + Claude Haiku 4.5 (키 보관)
```

### 상태 머신 (핵심)

화면 전환은 전부 `core/kiosk/kioskMachine.ts` 의 순수 reducer를 통합니다.

```
patrol ──WAKE──▶ home ──OPEN_MAP───▶ map  ─┐
                  │  ──OPEN_VOICE──▶ voice ┼─ START_GUIDING ─▶ guiding
                  ▲  ◀──── GO_HOME ────────┘                     │
                  └──────── END_GUIDING / IDLE_TIMEOUT ──────────┘ ▶ patrol
```

`staffCallActive` 는 화면과 직교(orthogonal)한 오버레이 플래그입니다.

### 음성 경로 (STT + LLM) — 백엔드 프록시

브라우저는 키를 들지 않습니다. 흐름:

```
브라우저(UI) ──/api/soniox/temporary-api-key──▶ 프록시 ──Bearer SONIOX_API_KEY──▶ Soniox
브라우저 ──(임시키)── WebSocket ─────────────────────────────────────────────▶ Soniox stt-rt-v4
브라우저(UI) ──/api/llm/understand (발화+후보 POI)──▶ 프록시 ──@anthropic-ai/sdk──▶ Claude Haiku 4.5
                                                  ◀── { intent, poi_id, reply, language } (구조화 출력)
```

- **시설 의도(§2.5.1)** → POI 확인 후 `guideTo()` → 서버에 **IF-01** 통지
- **일반 질문(§2.5.2)** → 대화형 응답만 표시, **서버 통지 없음**
- **다국어(§2.5.3)** → STT `languageHints` + LLM이 사용자 언어로 응답 (`ko/en/ja/zh`)

### 나머지 서버를 끼우는 법

목을 실제 구현으로 교체하는 지점은 **`createServices.ts` 한 곳**입니다.

- `RosService` → roslibjs + rosbridge_websocket (Nav2 목표, `requestHandoff` #6)
- `NavigationService` → 실제 로봇 피드백 기반 진행/도착 이벤트
- `FmsService` → 실제 MQTT/HTTP 로 IF-01 전송 (현재 MockFmsService 가 JSON 로깅)

UI 코드는 인터페이스에만 의존하므로 화면/로직 수정 없이 교체됩니다.

---

## 요구사항 → 구현 매핑

| # | 요구사항 | 구현 위치 |
|---|---------|----------|
| 1 | 크롬 크롬/작업표시줄 없는 키오스크 | 실행 `--kiosk`(README) + `core/hooks/useKioskMode` + `styles/global.css` |
| 2 | 순찰 시 웃는 얼굴 + "사용할거면 아무키나 누르세요" | `features/patrol` + `components/RobotFace` |
| 3 | 초기화면 큰 버튼 2개 + 우하단 [직원 호출] | `features/home` + `components/StaffCallButton` |
| 4 | 버튼 A: 도면형 지도, 시설 클릭 시 이동 | `features/map` (`Blueprint` SVG) → `NavigationService` |
| 5 | 버튼 B: STT+LLM으로 시설 도출 후 이동 | `features/voice` (`useVoiceFlow`) → `Stt/Llm/NavigationService` |
| 6 | 다른 층 시설이면 환승점 이동 + 다음 층 로봇 인계 | `MockNavigationService.planRoute/start` (`requestHandoff`) |
| 7 | 안내 중 웃는 얼굴 + "시설 안내중" | `features/guiding` |
| 8 | 텍스트/버튼 최대한 크게 | `styles/tokens.css` (clamp 기반 대형 스케일) |
| 9 | 버튼 A/B 짧은 이름 | "시설 안내" / "음성 안내" (`config/strings`) |
| 10 | 안내 종료 후 다시 순찰 | `GuidanceProvider` → `END_GUIDING` |
| 11 | [직원 호출] 팝업, 직원이 닫기로 종료 | `app/StaffCallOverlay` + `components/Modal` |

> 데모용 타이밍(이동/핸드오프/도착 유지 시간)과 이 로봇이 어느 층인지(`currentFloorId`)는
> `src/config/kiosk.config.ts` 에서 조정합니다. 음성 목(MockStt)은 정해진 예시 문장을 순환 재생합니다.

---

## ver02 요구사항 → 구현 매핑

| ver02 | 요구 | 구현 위치 |
|------|------|----------|
| 2.1 | 1F/2F Alfred가 자기 층 인지 (분리 빌드) | `config/env`(`VITE_FLOOR`) → `kiosk.config`(robot2/robot4) · `dev:2f`/`build:2f` |
| 2.2 | 이동 중 안내 화면 | `features/guiding` |
| 2.3 | 상호작용 2개(시설/음성) | `features/home` 버튼 A/B |
| 2.4 | 지도·리스트 클릭 → escort | `features/map` → `GuidanceProvider.guideTo` → IF-01 |
| 2.5 | 음성: STT→LLM | `features/voice/useVoiceFlow` |
| 2.5.1 | 시설 요청 → 서버 통지 | LLM intent=`facility` → 확인 → IF-01 |
| 2.5.2 | 무관한 질문 → 자유 응답(통지 X) | LLM intent=`chat` → 응답 표시만 |
| 2.5.3 | 한·영·일·중 | `core/i18n` + Soniox `languageHints` + LLM 응답 언어 |
| 1.5.1 | 층간 얼굴 인계 CV | **다음 단계(보류)** — 모델 조사 후 웹캠 캡처+임베딩+인계 |

> STT=**Soniox stt-rt-v4**, LLM=**Claude Haiku 4.5**(구조화 출력으로 intent/POI 판별). 키는 프록시에만.

---

## 기술 스택

React 18 · TypeScript(strict) · Vite 6 · CSS Modules + 디자인 토큰.
음성: `@soniox/speech-to-text-web`(브라우저). 프록시(`server/`): Express + `@anthropic-ai/sdk`(Haiku 4.5) + zod.
