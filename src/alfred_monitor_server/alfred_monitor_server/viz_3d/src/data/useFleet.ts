// FMS API(/api/robots, /api/missions, /api/events) 폴링 + 미연결 시 목업 폴백.
// 로봇 pose를 씬 좌표로 변환하고, 최근 위치를 누적해 이동 경로(trail)를 만든다.
import { useEffect, useRef, useState } from "react";
import { rosHeading, rosToScene, ROBOT_FLOOR } from "../config/transform";
import type { FleetSnapshot, PersonMarker, RobotMarker, Vec2 } from "../config/types";
import { mockPeople, mockRobots } from "./mock";

const POLL_MS = 1000;
const TRAIL_MAX = 60;

// FMS 로그인 자격(LAN 데모 기본값 — 필요 시 .env로 교체)
const FMS_USER = (import.meta as any).env?.VITE_FMS_USER ?? "admin";
const FMS_PASS = (import.meta as any).env?.VITE_FMS_PASS ?? "admin1234";

// 동시 로그인 중복 방지
let loginInFlight: Promise<void> | null = null;
async function ensureLogin(): Promise<void> {
  if (!loginInFlight) {
    const body = new URLSearchParams({ user: FMS_USER, password: FMS_PASS });
    loginInFlight = fetch("/login", {
      method: "POST", body, credentials: "same-origin", redirect: "manual",
    })
      .then(() => undefined)
      .catch(() => undefined)
      .finally(() => { loginInFlight = null; });
  }
  return loginInFlight;
}

// 401이면 로그인 후 1회 재시도하는 GET
async function authedFetch(path: string): Promise<Response> {
  let res = await fetch(path, { cache: "no-store", credentials: "same-origin" });
  if (res.status === 401) {
    await ensureLogin();
    res = await fetch(path, { cache: "no-store", credentials: "same-origin" });
  }
  return res;
}

interface ApiRobot {
  robot_id: string;
  state: string | null;
  pose?: { x?: number; y?: number; theta?: number };
  battery?: number | null;
  last_seen?: string;
  current_task_id?: string | null;
}

function ageSec(iso?: string): number {
  if (!iso) return Infinity;
  return (Date.now() - new Date(iso).getTime()) / 1000;
}

export function useFleet(): FleetSnapshot {
  const [snap, setSnap] = useState<FleetSnapshot>({
    robots: [], people: [], source: "mock", connected: false, updatedAt: Date.now(),
  });
  // 실서버 trail 누적(목업은 자체 trail 보유)
  const trails = useRef<Record<string, Vec2[]>>({});
  const roles = useRef<Record<string, "start" | "next" | null>>({});

  useEffect(() => {
    let alive = true;
    let timer: number;

    async function tick() {
      let ok = false;
      try {
        const [rRes, mRes] = await Promise.all([
          authedFetch("/api/robots"),
          authedFetch("/api/missions").catch(() => null),
        ]);
        if (rRes.ok) {
          const robots: ApiRobot[] = await rRes.json();
          // 활성 미션에서 역할(start/next) 추출
          if (mRes && mRes.ok) {
            try {
              const md = await mRes.json();
              const act = (md.active && md.active[0]) || null;
              roles.current = {};
              if (act) {
                if (act.start_robot) roles.current[act.start_robot] = "start";
                if (act.next_robot) roles.current[act.next_robot] = "next";
              }
            } catch { /* ignore */ }
          }
          const mapped: RobotMarker[] = robots.map((r) => {
            const floor = ROBOT_FLOOR[r.robot_id] ?? "1F";
            const x = r.pose?.x ?? 0;
            const y = r.pose?.y ?? 0;
            const pos = rosToScene(floor, x, y);
            const t = trails.current[r.robot_id] ?? (trails.current[r.robot_id] = []);
            const last = t[t.length - 1];
            if (!last || Math.hypot(last[0] - pos[0], last[1] - pos[1]) > 0.2) t.push(pos);
            if (t.length > TRAIL_MAX) t.shift();
            return {
              id: r.robot_id, floor, pos,
              heading: rosHeading(floor, r.pose?.theta ?? 0),
              state: r.state ?? "?",
              battery: r.battery ?? null,
              online: ageSec(r.last_seen) <= 10,
              role: roles.current[r.robot_id] ?? null,
              trail: [...t],
            };
          });
          if (alive) {
            setSnap({
              robots: mapped,
              people: mockPeople(Date.now()), // 사람은 FMS에 없음 → 목업(현장 트래커로 교체)
              source: "fms", connected: true, updatedAt: Date.now(),
            });
          }
          ok = true;
        }
      } catch { /* 연결 실패 → 폴백 */ }

      if (!ok && alive) {
        const now = Date.now();
        setSnap({
          robots: mockRobots(now), people: mockPeople(now),
          source: "mock", connected: false, updatedAt: now,
        });
      }
      if (alive) timer = window.setTimeout(tick, POLL_MS);
    }

    tick();
    return () => { alive = false; window.clearTimeout(timer); };
  }, []);

  return snap;
}
