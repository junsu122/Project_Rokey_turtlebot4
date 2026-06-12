// 이미지 1(실제 2D 평면도)의 구조·동선을 3D 씬 좌표로 인코딩.
// 좌표계: x = 오른쪽, z = 아래(평면 깊이), y = 높이. 단위 m.
// 두 층 모두 24×16 바운드. E/V(엘리베이터)는 양 층 동일 위치(12,6)에 둬서
// 층간 릴레이 핸드오버 지점이 수직으로 정렬되게 한다.
import type { FloorPlan } from "./types";

const ROOM_H: Record<string, number> = {
  boarding: 2.6,
  gate: 1.4,
  waiting: 0.9,
  transfer: 0.9,
  ticket: 1.6,
  stairs: 2.0,
  info: 1.6,
  elevator: 3.0,
  escalator: 1.8,
  wc: 2.4,
  entrance: 2.2,
};

export const ELEVATOR_POS: [number, number] = [12, 6];

// ── 1층 ──────────────────────────────────────────────────────────────────
// 출입구(좌상·중하), 안내(중앙), E/V(중앙), 에스컬레이터(우상·좌하), WC(좌), 대기(중하)
export const FLOOR_1F: FloorPlan = {
  id: "1F",
  name: "1층 전체 지도",
  bounds: [24, 16],
  rooms: [
    { id: "1f-ent-a", label: "출입구", type: "entrance", pos: [3.5, 2.2], size: [3.4, 2.2] },
    { id: "1f-wc", label: "WC", type: "wc", pos: [3.2, 11], size: [3.6, 4.2] },
    { id: "1f-esc-l", label: "escalator", type: "escalator", pos: [4.5, 14.4], size: [5.2, 2.0] },
    { id: "1f-info", label: "안내", type: "info", pos: [9.5, 8.2], size: [3.0, 2.0] },
    { id: "1f-ev", label: "E/V", type: "elevator", pos: ELEVATOR_POS, size: [2.6, 2.6] },
    { id: "1f-wait", label: "대기", type: "waiting", pos: [11, 13], size: [3.2, 2.2] },
    { id: "1f-ent-b", label: "출입구", type: "entrance", pos: [15.5, 13], size: [3.2, 2.2] },
    { id: "1f-esc-r", label: "escalator", type: "escalator", pos: [20, 4], size: [5.4, 2.2] },
    { id: "1f-stairs", label: "계단구", type: "stairs", pos: [7.5, 3.2], size: [2.4, 2.0] },
  ],
  pois: {
    EV: ELEVATOR_POS,
    ENT_A: [3.5, 2.2],
    ENT_B: [15.5, 13],
    INFO: [9.5, 8.2],
    ESC_R: [20, 4],
    BASE: [3.5, 4.5], // robot2 대기/복귀 지점(station)
  },
};

// ── 2층 ──────────────────────────────────────────────────────────────────
// 탑승구(좌), A-1/2/3(상단 게이트), 대기(우상), 환승(우, 좌석), 개찰구(좌하), 계단구
export const FLOOR_2F: FloorPlan = {
  id: "2F",
  name: "2층 전체 지도",
  bounds: [24, 16],
  rooms: [
    { id: "2f-boarding", label: "탑승구", type: "boarding", pos: [3, 7], size: [4.0, 11.0] },
    { id: "2f-a1", label: "A-1", type: "gate", pos: [8.5, 2.6], size: [3.2, 1.5] },
    { id: "2f-a2", label: "A-2", type: "gate", pos: [8.5, 4.6], size: [3.2, 1.5] },
    { id: "2f-a3", label: "A-3", type: "gate", pos: [8.5, 6.6], size: [3.2, 1.5] },
    { id: "2f-wait", label: "대기", type: "waiting", pos: [15, 2.8], size: [5.4, 3.0] },
    { id: "2f-transfer", label: "환승", type: "transfer", pos: [19.5, 9], size: [5.4, 9.5] },
    { id: "2f-ticket", label: "개찰구", type: "ticket", pos: [4.5, 13.5], size: [4.2, 2.2] },
    { id: "2f-ev", label: "E/V", type: "elevator", pos: ELEVATOR_POS, size: [2.6, 2.6] },
    { id: "2f-stairs", label: "계단구", type: "stairs", pos: [2.2, 11.5], size: [2.4, 2.2] },
  ],
  pois: {
    EV: ELEVATOR_POS,
    BOARDING: [3, 7],
    A1: [8.5, 2.6],
    A2: [8.5, 4.6],
    A3: [8.5, 6.6],
    TRANSFER: [19.5, 9],
    TICKET: [4.5, 13.5],
    BASE2: [4.5, 11.5], // robot4 대기/복귀 지점(station2)
  },
};

export const FLOORS: Record<string, FloorPlan> = {
  "1F": FLOOR_1F,
  "2F": FLOOR_2F,
};

export const roomHeight = (type: string) => ROOM_H[type] ?? 1.5;
