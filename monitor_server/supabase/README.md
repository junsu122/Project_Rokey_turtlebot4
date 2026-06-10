# Supabase + Vercel 외부 대시보드

로컬 모니터 서버를 **외부에서 볼 수 있는** 구조로 올리기 위한 자료. DB는 Supabase
(Postgres), UI는 Vercel(정적 호스팅), ROS2 수집은 LAN의 로컬 브리지가 그대로 담당한다.

```
로봇 --ROS2--> [로컬 브리지 main.py(FMS_BACKEND=supabase)] --HTTPS--> Supabase Postgres
                                                                         ▲ Realtime / RPC
외부 브라우저 --- Vercel(web-vercel/) --- supabase-js (로그인 후 읽기/조치) ---┘
```

> ⚠ **ROS2는 클라우드로 못 옮긴다.** DDS는 LAN 전용이라 Vercel이 토픽을 구독할 수 없다.
> 그래서 로봇과 같은 망의 PC에서 브리지(`main.py`)가 계속 떠 있어야 한다.
> 영상(WebRTC)은 이 단계 범위 밖 — 외부에서 보려면 TURN 서버가 별도로 필요하다.

## 1. Supabase 프로젝트 준비

1. supabase.com 에서 프로젝트 생성.
2. SQL Editor 에서 순서대로 실행:
   - `supabase/01_schema.sql` — 테이블 5개 + 인덱스 + Realtime + RLS
   - `supabase/02_functions.sql` — 집계 RPC(get_robots/get_stats/get_system/search_monitor/resolve_event) + robots 메타
   - `supabase/03_grants.sql` — 역할별 테이블 GRANT (service_role 전체 / authenticated 읽기 / anon 차단)
     · RLS 정책만으로는 PostgREST가 401/403 을 내므로 GRANT 가 반드시 필요
3. Authentication > Users 에서 관제 운영자 계정(이메일+비밀번호) 추가.
   (기존 `admin/admin1234` 대체. 이메일 형식 필요.)

RLS는 **로그인한(authenticated) 사용자에게만** 읽기를 허용한다. anon 키만으로는
아무 데이터도 못 읽으므로 로그인 게이트가 그대로 유지된다.

## 2. 로컬 브리지 (LAN PC)

```bash
cd monitor_server
cp .env.example .env          # SUPABASE_URL / SUPABASE_SERVICE_KEY 채우기
set -a; source .env; set +a
source /opt/ros/humble/setup.bash && source ../install/setup.bash
export ROS_DOMAIN_ID=2
python3 main.py               # FMS_BACKEND=supabase -> Supabase로 write-only 펌프
```

- `FMS_BACKEND=supabase` 면 Flask(로컬 5000)는 뜨지 않는다. ROS2 수신 → Supabase upsert만.
- `FMS_BACKEND=sqlite`(기본) 면 기존 로컬 대시보드(http://localhost:5000)가 그대로 동작.
- **service_role 키는 이 PC에만** 둔다. 브라우저/Vercel로 절대 보내지 않는다(RLS 우회 키).

## 3. Vercel UI (web-vercel/)

1. `web-vercel/supabase-config.js` 의 `url` / `anonKey` 를 채운다(둘 다 공개값 — anon 키는
   RLS 때문에 단독으로는 읽기 불가).
2. Vercel 에 `monitor_server/web-vercel` 디렉터리를 정적 배포:
   ```bash
   cd monitor_server/web-vercel
   vercel            # 또는 GitHub 연동 후 Root Directory = monitor_server/web-vercel
   ```
3. 배포 URL 접속 → 로그인(2단계에서 만든 계정) → 대시보드.

## 매핑 (기존 Flask API → Supabase)

| 기존 `/api/*` | 대체 |
| --- | --- |
| `/api/robots` | `rpc('get_robots')` |
| `/api/events`, `?active=1` | `sb.from('events').select(...)` |
| `/api/robot_log` | `sb.from('robot_status_log').select(...)` |
| `/api/stats` | `rpc('get_stats')` |
| `/api/system` | `rpc('get_system')` (ros/db 필드는 클라이언트에서 채움) |
| `/api/search` | `rpc('search_monitor')` |
| `POST /api/events/<id>/resolve` | `rpc('resolve_event')` |
| 로그인/세션 | Supabase Auth |
| 폴링(2s) | Realtime 구독 + 5s 새로고침(online 신선도용) |

## 이벤트 조치완료(resolve) 동기화 — Option A (이벤트 Supabase 단일 소스)

보안팀(Vercel)이 이벤트를 조치완료하면 로컬 관제 모니터에서도 자동으로 사라지게(양방향) 하는 구성.
이벤트는 **Supabase가 단일 소스**다. 로컬 대시보드도 이벤트 목록/조치완료/active 카운트를 Supabase에서
읽고 쓴다(로봇 상태·usage 는 로컬 SQLite 유지).

- 동작 조건: 로컬 서버 env 에 `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` 가 있으면 `api.py` 가 이벤트를
  Supabase 로 라우팅한다(`store.SupabaseStore.list_events/resolve_event/event_stats`). 없으면 기존 SQLite.
- 두 프로세스 실행:
  ```bash
  # 터미널 A — 펌프: ROS2 → Supabase (이벤트를 양 대시보드가 읽음)
  set -a; source .env; set +a            # FMS_BACKEND=supabase
  FMS_BACKEND=supabase python3 main.py

  # 터미널 B — 로컬 관제: localhost:5000 (이벤트는 Supabase, 로봇/usage 는 SQLite)
  set -a; source .env; set +a            # SUPABASE_URL/KEY 제공
  FMS_BACKEND=sqlite python3 main.py     # ← sqlite 로 덮어써서 Flask 서빙
  ```
- 결과: 누가 어디서 조치완료를 눌러도 같은 Supabase 행이 `resolved=1` 이 되어 양쪽 active 목록에서 빠진다.
- 로컬 SQLite 이벤트 적재는 오프라인 백업으로 계속됨(표시는 Supabase). 오프라인 폴백 표시는 미구현.

## 3D 관제 뷰 (web-vercel/viz/)

`viz_3d` 를 `web-vercel/viz/` 로 번들. 대시보드 iframe `./viz/?norobot` 로 임베드.
- floor_data / maps → `web-vercel/viz/maps/` 정적 스냅샷(빌드 시점 고정)
- robots / events → supabase (`get_robots` RPC + `events` 쿼리)
- iframe 은 같은 오리진 localStorage 로 부모 대시보드의 로그인 세션 공유
- ⚠ 외부에선 건물 레이아웃 편집이 localStorage 전용(서버 저장 없음). 정적 맵을 바꾸려면
  `web-vercel/viz/maps/floor_data.json` 갱신 후 재배포.

## 미포함 (다음 단계)

- **영상(WebRTC)**: LAN P2P 전제라 외부에선 TURN 서버 필요. `video_sources.json` 만 정적 제공.
