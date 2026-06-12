// 사람 마커 — 작은 캡슐(머리+몸). 이상감지(alert)는 적색 + 펄스 링.
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh } from "three";
import type { PersonMarker as PM } from "../config/types";
import { C } from "./theme";

export default function PersonMarker({ person }: { person: PM }) {
  const ring = useRef<Mesh>(null);
  const alert = person.kind === "alert";
  const color = alert ? C.personAlert : C.person;
  const [x, z] = person.pos;

  useFrame((s) => {
    if (ring.current && alert) {
      const p = 1 + Math.sin(s.clock.elapsedTime * 5) * 0.25;
      ring.current.scale.set(p, p, p);
    }
  });

  return (
    <group position={[x, 0, z]}>
      {alert && (
        <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
          <ringGeometry args={[0.4, 0.55, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.8} />
        </mesh>
      )}
      <mesh position={[0, 0.32, 0]} castShadow>
        <capsuleGeometry args={[0.16, 0.34, 4, 12]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={alert ? 0.6 : 0.2} roughness={0.5} />
      </mesh>
    </group>
  );
}
