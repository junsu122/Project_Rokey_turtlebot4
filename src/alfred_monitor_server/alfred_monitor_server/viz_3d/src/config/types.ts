// 공용 타입 — 씬/데이터 계층이 공유.

export type FloorId = "1F" | "2F";

export type Vec2 = [number, number]; // [x, z] (평면) — 단위 m

export type RoomType =
  | "boarding" // 탑승구
  | "gate" // A-1/A-2/A-3 개표 게이트
  | "waiting" // 대기
  | "transfer" // 환승(좌석)
  | "ticket" // 개찰구
  | "stairs" // 계단구
  | "info" // 안내
  | "elevator" // E/V
  | "escalator" // 에스컬레이터
  | "wc" // 화장실
  | "entrance"; // 출입구

export interface Room {
  id: string;
  label: string;
  type: RoomType;
  pos: Vec2; // 중심
  size: Vec2; // [폭(x), 깊이(z)]
  h?: number; // 높이(m), 기본 type별
}

export interface POI {
  id: string;
  pos: Vec2;
}

export interface FloorPlan {
  id: FloorId;
  name: string;
  bounds: Vec2; // [폭, 깊이]
  rooms: Room[];
  pois: Record<string, Vec2>; // 경로 계획용 명명 지점
}

// ── 런타임 마커(데이터 계층이 채움) ──────────────────────────────────────
export interface RobotMarker {
  id: string;
  floor: FloorId;
  pos: Vec2;
  heading: number; // rad
  state: string;
  battery: number | null;
  online: boolean;
  role?: "start" | "next" | null;
  trail: Vec2[]; // 최근 위치 누적 → 이동 경로 시각화
}

export interface PersonMarker {
  id: string;
  floor: FloorId;
  pos: Vec2;
  kind?: "normal" | "alert"; // alert = 이상감지(SUSPICIOUS_PERSON)
}

export interface CCTVMarker {
  id: string;
  floor: FloorId;
  pos: Vec2;
  dir: number; // 바라보는 방향(rad)
  fov: number; // 화각(rad)
  range: number; // 시야 거리(m)
}

export interface FleetSnapshot {
  robots: RobotMarker[];
  people: PersonMarker[];
  source: "fms" | "mock";
  connected: boolean;
  updatedAt: number;
}
