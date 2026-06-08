# FMS 3D 관제 모니터링 UI

실제 건물 평면도(이미지 1)의 구조·동선을 유지하고, 다크 sci-fi 아이소메트릭 스타일(이미지 2)을
적용한 **3D 관제 모니터링 대시보드**. React + Three.js(react-three-fiber).

## 기능
- **3D 아이소메트릭** 층 뷰 (직교 카메라 + Bloom 글로우)
- **TurtleBot4 위치** 표시 (헤딩·상태·배터리·역할)
- **사람 위치** 표시 (이상감지 인원은 적색 펄스)
- **CCTV 위치** + 시야(FOV) 콘
- **로봇 이동 경로** 시각화 (trail 폴리라인 + 흐르는 점)
- **1층 / 2층 전환** (상단 탭)
- **1920×1080** 고정 스테이지 (뷰포트에 맞춰 등비 축소)

## 실행
```bash
cd viz_3d
npm install
npm run dev          # http://localhost:5173
```

## 데이터 소스
- 기본: **FMS API**(`/api/robots`, `/api/missions`)를 Vite 프록시로 폴링.
  - FMS 주소 변경: `VITE_FMS_URL=http://192.168.0.10:5000 npm run dev`
  - FMS가 안 떠 있으면 자동으로 **목업 시뮬레이터**(릴레이 에스코트 동선)로 폴백.
- **사람·CCTV**는 FMS에 없으므로 별도 정의:
  - CCTV: `src/config/cctv.ts` (현장 설치 위치로 교체)
  - 사람: 현재 목업(`src/data/mock.ts`). 실제 인원 트래커 연동 시 `useFleet.ts`에서 교체.

## 좌표 보정 (실로봇 연동 시)
`src/config/transform.ts`의 `rosToScene()` — ROS map 좌표(pose x,y)를 씬 좌표로 변환.
로봇을 E/V 등 알려진 지점에 세우고 pose를 읽어 `offset/scale/rotDeg/flipY`를 맞춘다.
robot_id→층 매핑(`ROBOT_FLOOR`): robot2=1F, robot4=2F (config.ROBOTS 기준).

## 평면도 좌표
`src/config/floorplan.ts` — 이미지 1의 방·동선을 24×16m 그리드로 인코딩.
E/V는 양 층 동일 위치(12,6)에 둬서 층간 릴레이 핸드오버 지점이 수직 정렬된다.

## 구조
```
src/
├── config/   floorplan(평면도) · cctv · transform(좌표변환) · types
├── data/     useFleet(FMS 폴링+폴백) · mock(시뮬레이터)
├── three/    Scene · FloorModel · RobotMarker · PersonMarker · CCTVMarker · PathLine
└── ui/       TopBar(층 전환) · SidePanel(현황) · Legend(주요 시설)
```
