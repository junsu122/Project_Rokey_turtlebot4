// 한 층의 바닥 슬래브 + 방(돌출 박스 + 시안 엣지) + 한글 라벨(Html).
import { Edges, Html } from "@react-three/drei";
import { roomHeight } from "../config/floorplan";
import type { FloorPlan, Room } from "../config/types";
import { C } from "./theme";

function roomColor(type: string): string {
  if (type === "elevator") return "#3a3a26";
  if (type === "escalator") return "#173a4a";
  if (type === "transfer") return "#1c3a52";
  return C.roomFill;
}
function edgeColor(type: string): string {
  if (type === "elevator") return C.elevator;
  if (type === "escalator") return C.escalator;
  if (type === "gate" || type === "ticket") return C.gate;
  return C.edge;
}

function RoomBox({ room }: { room: Room }) {
  const h = room.h ?? roomHeight(room.type);
  const [x, z] = room.pos;
  const [w, d] = room.size;
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, h / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial
          color={roomColor(room.type)}
          metalness={0.25}
          roughness={0.65}
          transparent
          opacity={0.92}
        />
        <Edges threshold={15} color={edgeColor(room.type)} />
      </mesh>
      {/* 라벨 — 브라우저 폰트라 한글 정상 표시 */}
      <Html position={[0, h + 0.5, 0]} center distanceFactor={26} zIndexRange={[10, 0]}>
        <div className={`room-label rl-${room.type}`}>{room.label}</div>
      </Html>
    </group>
  );
}

export default function FloorModel({ plan }: { plan: FloorPlan }) {
  const [W, D] = plan.bounds;
  return (
    <group>
      {/* 바닥 슬래브 */}
      <mesh position={[W / 2, -0.3, D / 2]} receiveShadow>
        <boxGeometry args={[W + 2, 0.6, D + 2]} />
        <meshStandardMaterial color={C.floorTop} metalness={0.3} roughness={0.8} />
        <Edges threshold={15} color={C.floorEdge} />
      </mesh>
      {/* 바닥 그리드 */}
      <gridHelper
        args={[Math.max(W, D) + 2, Math.max(W, D) + 2, C.grid, C.grid]}
        position={[W / 2, 0.02, D / 2]}
      />
      {plan.rooms.map((r) => (
        <RoomBox key={r.id} room={r} />
      ))}
    </group>
  );
}
