// 로봇 이동 경로 시각화 — trail 폴리라인(글로우) + 진행 방향으로 흐르는 점.
import { Line } from "@react-three/drei";
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, Vector3 as TVec3 } from "three";
import { Vector3 } from "three";
import type { Vec2 } from "../config/types";

export default function PathLine({ trail, color }: { trail: Vec2[]; color: string }) {
  const dot = useRef<Mesh>(null);
  const pts = useMemo<[number, number, number][]>(
    () => trail.map((p) => [p[0], 0.18, p[1]]),
    [trail],
  );
  const v3 = useMemo<TVec3[]>(() => pts.map((p) => new Vector3(...p)), [pts]);

  useFrame((s) => {
    if (!dot.current || v3.length < 2) return;
    const u = (s.clock.elapsedTime * 0.25) % 1;
    const seg = (v3.length - 1) * u;
    const i = Math.floor(seg);
    const t = seg - i;
    dot.current.position.lerpVectors(v3[i], v3[i + 1], t);
  });

  if (pts.length < 2) return null;
  return (
    <group>
      <Line points={pts} color={color} lineWidth={3} transparent opacity={0.55} dashed dashSize={0.5} gapSize={0.3} />
      <mesh ref={dot}>
        <sphereGeometry args={[0.14, 12, 12]} />
        <meshBasicMaterial color={color} />
      </mesh>
    </group>
  );
}
