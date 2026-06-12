/**
 * 맵 보정 — 로봇 맵 프레임 좌표(m)를 도면(blueprint) 비율 {u,v}로 변환.
 *
 * 각 층 실측 4 꼭짓점(`docs`의 "1층맵/2층맵 좌표" 이미지)을 도면 outline 사각형에
 * **아핀 매핑**한다. 좌상(tl)을 원점으로 두고 tr 방향을 u(가로 0..1), bl 방향을
 * v(세로 0..1; 도면은 아래로 증가)로 잡는다 — "비율로 잡기".
 *
 * 사용: poseToFraction(x, y, 'F1') → {u, v} → 도면좌표 = outline.x + u·w, outline.y + v·h.
 * 실측 꼭짓점이 바뀌면 아래 FLOOR_CORNERS만 갱신.
 */

interface FloorCorners {
  /** 좌상 (도면 좌상단에 대응). */
  tl: readonly [number, number];
  /** 우상 (u=1 방향). */
  tr: readonly [number, number];
  /** 좌하 (v=1 방향). */
  bl: readonly [number, number];
  /** 우하 — 검증용(변환엔 미사용). */
  br?: readonly [number, number];
}

/** 1층맵/2층맵 좌표 이미지에서 읽은 실측 꼭짓점(로봇 맵 프레임, m). */
const FLOOR_CORNERS: Record<string, FloorCorners> = {
  F1: {
    tl: [-8.5699, 3.4737],
    tr: [-0.923, 4.4461],
    br: [-0.52, 1.676],
    bl: [-8.167, 0.7256],
  },
  F2: {
    tl: [-3.55, 3.6],
    tr: [-0.014, 3.83],
    br: [0.134, 1.026],
    bl: [-3.3, 0.848],
  },
};

/**
 * 로봇 pose(m) → 도면 비율 {u, v}. tl 기준 (tr, bl) 비직교 기저로 분해하므로
 * 맵의 회전·기울기까지 반영된다. 보정값 없는 층이면 null.
 */
export function poseToFraction(
  x: number,
  y: number,
  floorId: string,
): { u: number; v: number } | null {
  const c = FLOOR_CORNERS[floorId];
  if (!c) return null;

  const [ax, ay] = c.tl;
  const e1x = c.tr[0] - ax;
  const e1y = c.tr[1] - ay; // u축(가로) 벡터
  const e2x = c.bl[0] - ax;
  const e2y = c.bl[1] - ay; // v축(세로) 벡터
  const det = e1x * e2y - e2x * e1y;
  if (Math.abs(det) < 1e-9) return null;

  // (x,y) - tl = u·e1 + v·e2 를 u,v 에 대해 풀기(Cramer).
  const px = x - ax;
  const py = y - ay;
  const u = (px * e2y - e2x * py) / det;
  const v = (e1x * py - px * e1y) / det;
  return { u, v };
}

/** 해당 층에 보정 데이터가 있는지. */
export function hasFloorCalibration(floorId: string): boolean {
  return floorId in FLOOR_CORNERS;
}
