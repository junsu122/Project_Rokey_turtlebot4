// CCTV 위치 — FMS API에 없으므로 여기서 정적 정의(현장 설치 위치로 교체).
import type { CCTVMarker } from "./types";

const DEG = Math.PI / 180;

export const CCTVS: CCTVMarker[] = [
  // 1F
  { id: "CCTV-1F-01", floor: "1F", pos: [2, 2], dir: -45 * DEG, fov: 70 * DEG, range: 7 },
  { id: "CCTV-1F-02", floor: "1F", pos: [12, 1.5], dir: 90 * DEG, fov: 70 * DEG, range: 8 },
  { id: "CCTV-1F-03", floor: "1F", pos: [22, 14], dir: 200 * DEG, fov: 70 * DEG, range: 8 },
  { id: "CCTV-1F-04", floor: "1F", pos: [2, 14], dir: -30 * DEG, fov: 70 * DEG, range: 7 },
  // 2F
  { id: "CCTV-2F-01", floor: "2F", pos: [2, 2], dir: -45 * DEG, fov: 70 * DEG, range: 8 },
  { id: "CCTV-2F-02", floor: "2F", pos: [22, 2], dir: 225 * DEG, fov: 70 * DEG, range: 9 },
  { id: "CCTV-2F-03", floor: "2F", pos: [22, 15], dir: 200 * DEG, fov: 70 * DEG, range: 9 },
];

export const cctvForFloor = (floor: string) => CCTVS.filter((c) => c.floor === floor);
