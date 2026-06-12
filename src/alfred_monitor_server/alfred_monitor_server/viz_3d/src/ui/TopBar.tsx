import { useEffect, useState } from "react";
import type { FleetSnapshot, FloorId } from "../config/types";

export default function TopBar({
  floor, onFloor, fleet,
}: {
  floor: FloorId;
  onFloor: (f: FloorId) => void;
  fleet: FleetSnapshot;
}) {
  const [clock, setClock] = useState("");
  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString("ko-KR")), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="topbar">
      <div className="brand">
        <span className="logo">◈</span>
        <div>
          <div className="brand-title">FMS 3D 관제 모니터링</div>
          <div className="brand-sub">다중 로봇 릴레이 에스코트 · 아이소메트릭 뷰</div>
        </div>
      </div>

      <div className="floor-toggle">
        {(["1F", "2F"] as FloorId[]).map((f) => (
          <button
            key={f}
            className={`ftab ${floor === f ? "active" : ""}`}
            onClick={() => onFloor(f)}
          >
            {f}
            <span className="ftab-sub">{f === "1F" ? "1층" : "2층"}</span>
          </button>
        ))}
      </div>

      <div className="conn">
        <span className={`src-badge ${fleet.source}`}>
          {fleet.source === "fms" ? "FMS 연결됨" : "목업 데이터"}
        </span>
        <span className="clock">{clock}</span>
      </div>
    </header>
  );
}
