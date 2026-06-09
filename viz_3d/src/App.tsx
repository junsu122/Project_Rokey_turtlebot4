import { useEffect, useState } from "react";
import type { FloorId } from "./config/types";
import { useFleet } from "./data/useFleet";
import Scene from "./three/Scene";
import Legend from "./ui/Legend";
import SidePanel from "./ui/SidePanel";
import TopBar from "./ui/TopBar";

// 1920×1080 고정 스테이지를 뷰포트에 맞춰 등비 축소.
function useStageScale() {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const fit = () => setScale(Math.min(window.innerWidth / 1920, window.innerHeight / 1080));
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);
  return scale;
}

const FLOOR_TAG: Record<FloorId, string> = {
  "1F": "1F · 1층 전체 지도",
  "2F": "2F · 2층 전체 지도",
};

// dashboard.html 등에 iframe 임베드용 — 사이드패널/풀 상단바 없이 씬만 꽉 채움.
function EmbedView({
  floor, setFloor, fleet,
}: {
  floor: FloorId;
  setFloor: (f: FloorId) => void;
  fleet: ReturnType<typeof useFleet>;
}) {
  return (
    <div className="embed-root">
      <Scene floor={floor} fleet={fleet} />
      <div className="embed-top">
        <span className="scene-tag">{FLOOR_TAG[floor]}</span>
        <span className={`src-badge ${fleet.source}`}>
          {fleet.source === "fms" ? "FMS 연결됨" : "목업 데이터"}
        </span>
      </div>
      <div className="floor-toggle embed-toggle">
        {(["1F", "2F"] as FloorId[]).map((f) => (
          <button key={f} className={`ftab ${floor === f ? "active" : ""}`} onClick={() => setFloor(f)}>
            {f}
            <span className="ftab-sub">{f === "1F" ? "1층" : "2층"}</span>
          </button>
        ))}
      </div>
      <div className="embed-legend">
        <span className="lm"><span className="dot robot" /> 로봇</span>
        <span className="lm"><span className="dot person" /> 사람</span>
        <span className="lm"><span className="dot cctv" /> CCTV</span>
        <span className="lm"><span className="dot path" /> 이동 경로</span>
      </div>
    </div>
  );
}

export default function App() {
  const [floor, setFloor] = useState<FloorId>("1F");
  const fleet = useFleet();
  const scale = useStageScale();
  const embed = typeof window !== "undefined" && new URLSearchParams(window.location.search).has("embed");

  if (embed) return <EmbedView floor={floor} setFloor={setFloor} fleet={fleet} />;

  return (
    <div className="viewport">
      <div className="stage" style={{ transform: `translate(-50%, -50%) scale(${scale})` }}>
        <TopBar floor={floor} onFloor={setFloor} fleet={fleet} />
        <main className="stage-main">
          <div className="scene-wrap">
            <Scene floor={floor} fleet={fleet} />
            <div className="scene-tag">{FLOOR_TAG[floor]}</div>
          </div>
          <SidePanel floor={floor} fleet={fleet} />
        </main>
        <Legend floor={floor} />
      </div>
    </div>
  );
}
