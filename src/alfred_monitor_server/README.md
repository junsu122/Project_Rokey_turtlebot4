# Monitoring Server (관제 서버)

로봇 상태·이상이벤트·키오스크 사용현황을 **관측만** 하는 서버. 임무 생성/지시/로봇 제어는 하지 않는다.
ROS2 메시지를 수신해 저장하고, 관제 대시보드를 제공한다.

- 로컬 관제: Flask + SQLite (`http://localhost:5000`)
- 외부 관제: **Supabase(클라우드 DB) + Vercel(정적 대시보드)** — 다른 LAN/인터넷에서 조회
- 둘은 **백엔드 한 줄(`FMS_BACKEND`)** 로 전환·병행한다.

---

## 1. 구조 한눈에

```
로봇 --DDS--> robot_state_publisher_node --/robotN/robot_state--> [monitor_server main.py]
              (amcl_pose+battery → RobotState)                          │
                                                                        ├─(sqlite) 로컬 SQLite ─> http://localhost:5000  (로컬 관제)
                                                                        └─(supabase) HTTPS ─> Supabase ─> Vercel  (외부 관제)
이벤트(알람)는 항상 Supabase 단일 소스(양쪽 공유). 영상(WebRTC)은 별도 트랙(§6).
```

> ⚠ DDS는 LAN 전용. 클라우드가 ROS 토픽을 직접 못 받으므로, **로봇과 같은 망의 PC에서 main.py가 상주**하며 수신→적재한다.

### ⭐ 가장 헷갈리는 점 — "로봇 데이터 출처"
| 화면 | 로봇 상태 출처 | 이벤트(알람) 출처 |
|---|---|---|
| **localhost:5000** (로컬 관제) | **로컬 SQLite** (`FMS_BACKEND=sqlite` 프로세스가 채움) | Supabase |
| **Vercel** (외부) | **Supabase** (`FMS_BACKEND=supabase` 펌프가 채움) | Supabase |

→ 로봇 상태는 두 화면이 **각자 소스**다. 한쪽 백엔드만 돌리면 그쪽 화면만 갱신된다.
→ **실제 운영에선 펌프와 로컬 관제가 둘 다 같은 ROS 토픽을 수신**하므로 SQLite·Supabase가 동시에 채워져 **양쪽 다 자동으로 움직인다.**

---

## 2. 사용방법 — 무엇을 띄울지 (3가지 역할)

| 목적 | 실행 | 화면 |
|---|---|---|
| **로컬에서만 관제** | `FMS_BACKEND=sqlite python3 main.py` | localhost:5000 |
| **외부(Vercel)로 내보내기** | `FMS_BACKEND=supabase python3 main.py` (펌프) | Vercel URL |
| **둘 다** (로컬 + 외부) | 위 두 개를 **각각 다른 터미널**에서 동시에 | 양쪽 |

- `FMS_BACKEND=sqlite` (기본): Flask(5000) 뜸 + 로컬 SQLite 적재. 단, `.env`에 `SUPABASE_*`가 있으면 **이벤트는 Supabase**에서 읽고 쓴다(조치완료 양방향 동기화).
- `FMS_BACKEND=supabase`: Flask **안 뜸**(write-only 펌프). ROS2 수신 → Supabase upsert만.

---

## 3. 실제 구동방법 (로봇 LAN PC)

### 3-0. 1회 준비
```bash
cd ~/alfred_ws
git checkout monitor2
colcon build --packages-select alfred_interfaces alfred_bridge alfred_vision alfred_driving --symlink-install
```
`.env` 작성 (`monitor_server/.env`, `.env.example` 복사):
```
FMS_BACKEND=supabase
SUPABASE_URL=https://<프로젝트ref>.supabase.co
SUPABASE_SERVICE_KEY=<service_role 키>   # 이 PC에만, 브라우저로 절대 X
FMS_STATUS_TIMEOUT=10.0
```
Supabase/Vercel 클라우드 셋업은 → [`supabase/README.md`](supabase/README.md)

### 3-1. 공통 환경 소싱 (모든 터미널)
```bash
cd ~/alfred_ws
source /opt/ros/humble/setup.bash && source install/setup.bash
unset ROS_DISCOVERY_SERVER
export ROS_DOMAIN_ID=2          # 로봇과 동일
```
> ⚠ 이 소싱을 빼면 `ModuleNotFoundError: No module named 'alfred_interfaces'` 가 난다.

### 3-2. 터미널 1 — robot_state 생성
실로봇의 `amcl_pose`/`battery_state`가 흐르는 상태에서:
```bash
ros2 run alfred_bridge robot_state_publisher_node
# → /robot2/robot_state, /robot4/robot_state (1Hz)
```
> 실로봇 토픽 목록엔 `/robotN/robot_state`가 없다. 이 노드가 `amcl_pose+battery_state`를 RobotState로 변환해 만들어 준다.

### 3-3. 터미널 2 — 펌프 (외부 Vercel용)
```bash
cd monitor_server
set -a; source .env; set +a            # FMS_BACKEND=supabase
python3 main.py
# 로그 "ROS2 ingest -> Supabase (no local API)" → 정상
```

### 3-4. 터미널 3 — 로컬 관제 (localhost:5000)
```bash
cd monitor_server
set -a; source .env; set +a
FMS_BACKEND=sqlite python3 main.py     # sqlite 모드여야 Flask가 뜸
```
접속: `http://localhost:5000` · 로그인 `admin / admin1234`(`.env`의 `FMS_ADMIN_*`로 변경)

### 3-5. 외부 조회 (Vercel)
배포 URL(예: `https://monitor-beige-five.vercel.app/`)을 **아무 망에서나** 열고 **Supabase Auth 계정**으로 로그인. 로봇 망과 무관하게 동작.

---

## 4. 동작 확인 / 테스트

```bash
# 토픽이 흐르는지
ros2 topic hz /robot2/robot_state

# Supabase 적재 확인 (read-only)
cd monitor_server; set -a; source .env; set +a
python3 -c "import store;sb=store.SupabaseStore();sb.init();print(sb._request('GET','/latest_robot_status?select=robot_id,state,battery,last_seen'))"
```
샌드박스/CI 등 **프로세스 간 DDS가 막힌 환경**에서의 적재 검증, 자세한 테스트 절차 →
[`../docs/실행_및_테스트_가이드_monitor2.md`](../docs/실행_및_테스트_가이드_monitor2.md)

---

## 5. 모듈 / 토픽 / 테이블

| 파일 | 역할 |
|---|---|
| `main.py` | ROS2 수신 + (sqlite 모드) Flask 기동 |
| `ros_ingest.py` | RobotState/Event/detection/info/information 구독 |
| `robot_registry.py` | 로봇 상태 적재(`store` 경유) |
| `event_service.py` / `usage_service.py` | 이벤트 / 키오스크 사용현황 적재 |
| `store.py` | 백엔드 추상화 (`sqlite`=db.py / `supabase`=PostgREST 펌프) |
| `db.py` | 로컬 SQLite |
| `api.py` | 읽기 전용 대시보드/API + 이벤트 resolve |
| `web/dashboard.html` | 로컬 관제 대시보드 |
| `web-vercel/` | 외부 대시보드(정적, supabase-js) |

**구독 토픽**: `/robotN/robot_state`, `/robotN/vision/alert`, `/robotN/detection/info`, `/information`
**테이블**: `latest_robot_status`, `robot_status_log`, `events`, `ui_usage_log`, `monitor_counters`

---

## 6. WebRTC 영상 수신 (⚠ 작업 중 · 미완성)

대시보드 **영상 탭**에서 로봇 카메라 라이브 영상. 미디어는 **로봇 ↔ 브라우저 P2P**(서버 우회),
서버는 시그널링 메타(`web/video_sources.json`)만 제공. **외부(다른 LAN)에서 보려면 TURN 서버 필요** — 현 단계 범위 밖.

### 로봇 측 실행 (각 로봇 PC)
```bash
pip install aiortc aiohttp opencv-python numpy        # 최초 1회
source /opt/ros/humble/setup.bash && source ~/alfred_ws/install/setup.bash
ros2 run alfred_vision video_sender_node \
  --ros-args -p image_topic:=/robot2/oakd/rgb/image_raw/compressed   # 실제 카메라 토픽으로
```
연결 확인(관제 PC): `curl -X POST http://<robot-ip>:8081/offer -d '{"sdp":"x","type":"offer"}' -H "Content-Type: application/json"`

### 남은 작업 (TODO)
- [ ] 로봇에서 `video_sender_node` 실제 구동/검증 (현재 8081 미응답 → end-to-end 미확인)
- [ ] `image_topic` 확정 (OAK-D 실제 압축 토픽명; 없으면 `image_transport republish`)
- [ ] 로봇 방화벽 8081 허용(`sudo ufw allow 8081`)
- [ ] 외부 시청용 TURN 서버, 자동 재연결, 다중 시청자
