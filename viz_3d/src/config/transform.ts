// ROS map 좌표(FMS pose: x, y meters) → 씬 좌표([x, z]) 변환.
// 실제 SLAM 맵 원점·스케일에 맞춰 보정해야 한다(아래 값은 데모 기본값).
// 보정 방법: 로봇을 알려진 지점(E/V 등)에 세우고 pose를 읽어 offset/scale을 맞춘다.
import type { FloorId, Vec2 } from "./types";

interface FloorTransform {
  scale: number; // m → m (보통 1)
  offset: Vec2; // 씬 좌표 평행이동
  flipY: boolean; // ROS y축 ↔ 씬 z축 부호
  rotDeg: number; // 회전(도)
}

// robot_id → 층 매핑 (config.ROBOTS: robot2=1F, robot4=2F)
export const ROBOT_FLOOR: Record<string, FloorId> = {
  robot2: "1F",
  robot4: "2F",
};

const TF: Record<FloorId, FloorTransform> = {
  "1F": { scale: 1, offset: [12, 8], flipY: true, rotDeg: 0 },
  "2F": { scale: 1, offset: [12, 8], flipY: true, rotDeg: 0 },
};

export function rosToScene(floor: FloorId, x: number, y: number): Vec2 {
  const t = TF[floor];
  const r = (t.rotDeg * Math.PI) / 180;
  const yy = t.flipY ? -y : y;
  const rx = x * Math.cos(r) - yy * Math.sin(r);
  const rz = x * Math.sin(r) + yy * Math.cos(r);
  return [rx * t.scale + t.offset[0], rz * t.scale + t.offset[1]];
}

export const rosHeading = (floor: FloorId, theta: number) =>
  (TF[floor].flipY ? -theta : theta) + (TF[floor].rotDeg * Math.PI) / 180;
