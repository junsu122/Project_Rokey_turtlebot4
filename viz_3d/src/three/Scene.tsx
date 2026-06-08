// 아이소메트릭 3D 씬.
// ⚠️ 직교(orthographic) 카메라는 현재 three/r3f 버전 조합에서 캔버스가 렌더되지 않는
//    문제가 있어, 원근 카메라를 멀리서 좁은 화각(fov)으로 두어 아이소메트릭처럼 보이게 한다.
//    평면도는 원점 중심으로 오프셋(-W/2,-D/2)해 OrbitControls target=[0,0,0]로 단순화.
import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import { cctvForFloor } from "../config/cctv";
import { FLOORS } from "../config/floorplan";
import type { FleetSnapshot, FloorId } from "../config/types";
import CCTVMarker from "./CCTVMarker";
import FloorModel from "./FloorModel";
import PathLine from "./PathLine";
import PersonMarker from "./PersonMarker";
import RobotMarker from "./RobotMarker";
import { C } from "./theme";

export default function Scene({ floor, fleet }: { floor: FloorId; fleet: FleetSnapshot }) {
  const plan = FLOORS[floor];
  const [W, D] = plan.bounds;
  const robots = fleet.robots.filter((r) => r.floor === floor);
  const people = fleet.people.filter((p) => p.floor === floor);
  const cams = cctvForFloor(floor);

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      gl={{ antialias: true }}
      camera={{ position: [58, 52, 58], fov: 22, near: 0.1, far: 600 }}
      onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
      style={{ background: C.bg }}
    >
      <OrbitControls
        target={[0, 0, 0]}
        enablePan
        enableZoom
        minDistance={30}
        maxDistance={160}
        minPolarAngle={Math.PI / 8}
        maxPolarAngle={Math.PI / 2.3}
      />

      <ambientLight intensity={0.7} />
      <hemisphereLight args={["#9fd6ff", "#0a1422", 0.6]} />
      <directionalLight position={[30, 50, 20]} intensity={1.2} castShadow shadow-mapSize={[2048, 2048]}>
        <orthographicCamera attach="shadow-camera" args={[-30, 30, 30, -30, 0.1, 160]} />
      </directionalLight>

      <Suspense fallback={null}>
        {/* 평면도 중심을 원점으로 이동 */}
        <group key={floor} position={[-W / 2, 0, -D / 2]}>
          <FloorModel plan={plan} />
          {cams.map((c) => (
            <CCTVMarker key={c.id} cam={c} />
          ))}
          {robots.map((r) => (
            <PathLine key={`${r.id}-trail`} trail={r.trail} color={C.path} />
          ))}
          {people.map((p) => (
            <PersonMarker key={p.id} person={p} />
          ))}
          {robots.map((r) => (
            <RobotMarker key={r.id} robot={r} />
          ))}
        </group>
      </Suspense>
    </Canvas>
  );
}
