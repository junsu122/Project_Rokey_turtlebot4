// ROS SLAM map 좌표(FMS pose: x, y meters) → 씬 좌표([x, z]) 변환.
// docs/maps/map_*.yaml 의 origin/resolution 과 이미지 크기를 기준으로 정규화한다.
import type { FloorId, Vec2 } from "./types";

interface MapMeta {
  origin: Vec2;
  resolution: number;
  width: number;
  height: number;
  rotDeg: number;
}

// robot_id → 층 매핑 (config.ROBOTS: robot2=1F, robot4=2F)
export const ROBOT_FLOOR: Record<string, FloorId> = {
  robot2: "1F",
  robot4: "2F",
};

const MAP_META: Record<FloorId, MapMeta> = {
  "1F": { origin: [-8.91, -0.179], resolution: 0.05, width: 175, height: 110, rotDeg: 0 },
  "2F": { origin: [-3.73, 0.551], resolution: 0.05, width: 81, height: 75, rotDeg: 0 },
};

const SCENE_BOUNDS: Record<FloorId, Vec2> = {
  "1F": [24, 16],
  "2F": [24, 16],
};

export function rosToScene(floor: FloorId, x: number, y: number): Vec2 {
  const m = MAP_META[floor];
  const [sceneW, sceneH] = SCENE_BOUNDS[floor];
  const mapW = m.width * m.resolution;
  const mapH = m.height * m.resolution;
  const nx = (x - m.origin[0]) / mapW;
  const ny = (y - m.origin[1]) / mapH;
  return [nx * sceneW, (1 - ny) * sceneH];
}

export const rosHeading = (floor: FloorId, theta: number) =>
  -theta + (MAP_META[floor].rotDeg * Math.PI) / 180;
