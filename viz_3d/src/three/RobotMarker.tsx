// TurtleBot4 양식화 마커 — 베이스 디스크 + 본체 + 헤딩 화살표 + 바닥 글로우 링 + 라벨.
import { Html } from "@react-three/drei";
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh } from "three";
import type { RobotMarker as RM } from "../config/types";
import { C } from "./theme";

export default function RobotMarker({ robot }: { robot: RM }) {
  const ring = useRef<Mesh>(null);
  const color = robot.role === "next" ? C.robotNext : C.robotStart;
  const [x, z] = robot.pos;

  useFrame((s) => {
    if (ring.current) {
      const p = 1 + Math.sin(s.clock.elapsedTime * 3) * 0.12;
      ring.current.scale.set(p, p, p);
    }
  });

  return (
    <group position={[x, 0, z]} rotation={[0, -robot.heading, 0]}>
      {/* 바닥 글로우 링 */}
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.06, 0]}>
        <ringGeometry args={[0.55, 0.72, 40]} />
        <meshBasicMaterial color={color} transparent opacity={0.85} />
      </mesh>
      {/* 베이스 디스크 (TurtleBot4 원형 베이스) */}
      <mesh position={[0, 0.12, 0]} castShadow>
        <cylinderGeometry args={[0.42, 0.45, 0.16, 32]} />
        <meshStandardMaterial color="#0f1c2c" metalness={0.4} roughness={0.5} />
      </mesh>
      {/* 본체 */}
      <mesh position={[0, 0.42, 0]} castShadow>
        <cylinderGeometry args={[0.34, 0.4, 0.5, 28]} />
        <meshStandardMaterial color={C.robotBody} emissive={color} emissiveIntensity={0.35} metalness={0.5} roughness={0.35} />
      </mesh>
      {/* 상단 센서탑 */}
      <mesh position={[0, 0.78, 0]} castShadow>
        <cylinderGeometry args={[0.12, 0.16, 0.2, 20]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
      </mesh>
      {/* 헤딩 화살표(+x = 정면) */}
      <mesh position={[0.62, 0.2, 0]} rotation={[0, 0, -Math.PI / 2]}>
        <coneGeometry args={[0.16, 0.4, 4]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {/* 라벨 */}
      <Html position={[0, 1.5, 0]} center distanceFactor={24} zIndexRange={[30, 10]}>
        <div className="robot-label" style={{ borderColor: color }}>
          <b style={{ color }}>{robot.id}</b>
          <span className="rl-state">{robot.state}</span>
          {robot.battery != null && <span className="rl-batt">{robot.battery}%</span>}
        </div>
      </Html>
    </group>
  );
}
