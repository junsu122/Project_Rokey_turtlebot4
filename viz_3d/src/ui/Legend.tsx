// 하단 "주요 시설" 범례 바 (이미지 2 스타일) — 활성 층의 시설 종류.
import { FLOORS } from "../config/floorplan";
import type { FloorId, RoomType } from "../config/types";

const ICON: Record<RoomType, string> = {
  boarding: "🚉", gate: "🚪", waiting: "🛋", transfer: "🔄", ticket: "🎫",
  stairs: "🪜", info: "ℹ️", elevator: "🛗", escalator: "↗️", wc: "🚻", entrance: "🚶",
};
const NAME: Record<RoomType, string> = {
  boarding: "탑승구", gate: "게이트", waiting: "대기", transfer: "환승", ticket: "개찰구",
  stairs: "계단구", info: "안내", elevator: "E/V", escalator: "에스컬레이터", wc: "화장실", entrance: "출입구",
};

export default function Legend({ floor }: { floor: FloorId }) {
  const types = Array.from(new Set(FLOORS[floor].rooms.map((r) => r.type)));
  return (
    <footer className="legend">
      <span className="legend-title">주요 시설</span>
      <div className="legend-items">
        {types.map((t) => (
          <span key={t} className="legend-item">
            <span className="li-ic">{ICON[t]}</span>
            {NAME[t]}
          </span>
        ))}
      </div>
      <div className="legend-markers">
        <span className="lm"><span className="dot robot" /> 로봇</span>
        <span className="lm"><span className="dot person" /> 사람</span>
        <span className="lm"><span className="dot cctv" /> CCTV</span>
        <span className="lm"><span className="dot path" /> 이동 경로</span>
      </div>
    </footer>
  );
}
