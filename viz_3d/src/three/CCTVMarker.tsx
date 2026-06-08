// CCTV 마커 — 폴 + 카메라 박스 + 시야(FOV) 콘(translucent).
import { Html } from "@react-three/drei";
import type { CCTVMarker as CM } from "../config/types";
import { C } from "./theme";

export default function CCTVMarker({ cam }: { cam: CM }) {
  const [x, z] = cam.pos;
  const h = 3.0; // 설치 높이
  // FOV 콘: 길이 range, 반경 = range*tan(fov/2). 콘은 +y가 기본축 → 눕혀서 dir 방향으로.
  const r = cam.range * Math.tan(cam.fov / 2);
  return (
    <group position={[x, 0, z]}>
      {/* 폴 */}
      <mesh position={[0, h / 2, 0]}>
        <cylinderGeometry args={[0.04, 0.04, h, 8]} />
        <meshStandardMaterial color="#3a4a5e" />
      </mesh>
      {/* 카메라 본체 */}
      <group position={[0, h, 0]} rotation={[0, -cam.dir, 0]}>
        <mesh position={[0.18, 0, 0]} castShadow>
          <boxGeometry args={[0.42, 0.22, 0.22]} />
          <meshStandardMaterial color={C.cctv} metalness={0.5} roughness={0.4} />
        </mesh>
        {/* FOV 콘 — 카메라에서 바닥 쪽으로 비스듬히 */}
        <group rotation={[0, 0, Math.PI / 2]}>
          <mesh position={[-cam.range / 2 + 0.1, 0, 0]} rotation={[0, 0, 0]}>
            <coneGeometry args={[r, cam.range, 24, 1, true]} />
            <meshBasicMaterial color={C.cctvFov} transparent opacity={0.12} side={2} />
          </mesh>
        </group>
      </group>
      <Html position={[0, h + 0.5, 0]} center distanceFactor={30} zIndexRange={[20, 5]}>
        <div className="cctv-label">📷 {cam.id.replace(/^CCTV-/, "")}</div>
      </Html>
    </group>
  );
}
