// FMS 미연결 시 사용하는 목업 시뮬레이터 — 로봇 2대가 E/V 경유로
// 층간 릴레이 에스코트하는 동선 + 사람 보행을 만든다.
import { ELEVATOR_POS, FLOOR_1F, FLOOR_2F } from "../config/floorplan";
import type { PersonMarker, RobotMarker, Vec2 } from "../config/types";

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerp2 = (a: Vec2, b: Vec2, t: number): Vec2 => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];
const headingOf = (a: Vec2, b: Vec2) => Math.atan2(b[1] - a[1], b[0] - a[0]);

// 다구간 경로를 따라 0..1 진행률로 위치/방향 계산
function alongPath(path: Vec2[], u: number): { pos: Vec2; heading: number } {
  if (path.length < 2) return { pos: path[0] ?? [0, 0], heading: 0 };
  const seg = (path.length - 1) * Math.min(0.999, Math.max(0, u));
  const i = Math.floor(seg);
  const t = seg - i;
  return { pos: lerp2(path[i], path[i + 1], t), heading: headingOf(path[i], path[i + 1]) };
}

// robot2(1F): 출입구 → E/V (핸드오버 지점으로 에스코트)
const PATH_R2: Vec2[] = [FLOOR_1F.pois.ENT_B, FLOOR_1F.pois.INFO, ELEVATOR_POS];
// robot4(2F): E/V → 환승 (인수 후 최종 목적지로)
const PATH_R4: Vec2[] = [ELEVATOR_POS, [14, 7], FLOOR_2F.pois.TRANSFER];

const trails: Record<string, Vec2[]> = { robot2: [], robot4: [] };
function pushTrail(id: string, p: Vec2): Vec2[] {
  const t = trails[id];
  const last = t[t.length - 1];
  if (!last || Math.hypot(last[0] - p[0], last[1] - p[1]) > 0.25) t.push(p);
  if (t.length > 60) t.shift();
  return [...t];
}

export function mockRobots(now: number): RobotMarker[] {
  const cycle = (now / 14000) % 1; // 14초 주기
  // 전반부: robot2가 E/V로 이동, robot4 대기 → 후반부: robot4가 환승으로 이동
  const u2 = Math.min(1, cycle * 1.6);
  const u4 = Math.max(0, (cycle - 0.55) * 2.2);
  const r2 = alongPath(PATH_R2, u2);
  const r4 = u4 <= 0 ? { pos: ELEVATOR_POS, heading: Math.PI / 2 } : alongPath(PATH_R4, u4);

  return [
    {
      id: "robot2", floor: "1F", pos: r2.pos, heading: r2.heading,
      state: u2 < 1 ? "ESCORTING" : "WAITING_HANDOVER", battery: 92, online: true,
      role: "start", trail: pushTrail("robot2", r2.pos),
    },
    {
      id: "robot4", floor: "2F", pos: r4.pos, heading: r4.heading,
      state: u4 <= 0 ? "HANDOVER_READY" : u4 < 1 ? "ESCORTING" : "RETURNING",
      battery: 78, online: true, role: "next", trail: pushTrail("robot4", r4.pos),
    },
  ];
}

const PEOPLE_SEED: { floor: "1F" | "2F"; base: Vec2; amp: Vec2; phase: number }[] = [
  { floor: "1F", base: [13, 11], amp: [2.5, 1.2], phase: 0 },
  { floor: "1F", base: [9, 9], amp: [1.5, 2.0], phase: 1.7 },
  { floor: "1F", base: [19, 5], amp: [2.0, 1.0], phase: 3.1 },
  { floor: "2F", base: [15, 4], amp: [2.2, 1.4], phase: 0.6 },
  { floor: "2F", base: [18, 10], amp: [1.8, 2.4], phase: 2.3 },
  { floor: "2F", base: [9, 5], amp: [1.2, 1.5], phase: 4.0 },
];

export function mockPeople(now: number): PersonMarker[] {
  const t = now / 2600;
  return PEOPLE_SEED.map((p, i) => ({
    id: `P-${i + 1}`,
    floor: p.floor,
    pos: [p.base[0] + Math.cos(t + p.phase) * p.amp[0], p.base[1] + Math.sin(t * 1.3 + p.phase) * p.amp[1]] as Vec2,
    kind: i === 2 ? "alert" : "normal",
  }));
}
