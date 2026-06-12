import { cctvForFloor } from "../config/cctv";
import type { FleetSnapshot, FloorId } from "../config/types";

const STATE_COLOR: Record<string, string> = {
  ESCORTING: "#39f3c6", WAITING_HANDOVER: "#ffb24a", HANDOVER_READY: "#ffb24a",
  RESERVED: "#ffb24a", RETURNING: "#6aa6ff", PATROL: "#7f8aa0", IDLE: "#7f8aa0",
  EMERGENCY: "#ff5a5a", ERROR: "#ff5a5a",
};

export default function SidePanel({ floor, fleet }: { floor: FloorId; fleet: FleetSnapshot }) {
  const robots = fleet.robots.filter((r) => r.floor === floor);
  const people = fleet.people.filter((p) => p.floor === floor);
  const alerts = people.filter((p) => p.kind === "alert");
  const cams = cctvForFloor(floor);

  return (
    <aside className="side">
      <section className="card">
        <h3>현황 · {floor}</h3>
        <div className="stat-row">
          <div className="stat"><span className="stat-n">{robots.length}</span><span className="stat-l">로봇</span></div>
          <div className="stat"><span className="stat-n">{people.length}</span><span className="stat-l">사람</span></div>
          <div className="stat"><span className="stat-n">{cams.length}</span><span className="stat-l">CCTV</span></div>
          <div className={`stat ${alerts.length ? "danger" : ""}`}>
            <span className="stat-n">{alerts.length}</span><span className="stat-l">이상</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>로봇 (TurtleBot4)</h3>
        {robots.length === 0 && <div className="muted">이 층에 로봇 없음</div>}
        {robots.map((r) => (
          <div key={r.id} className="robot-row">
            <span className={`rdot ${r.online ? "on" : "off"}`} />
            <span className="rid">{r.id}</span>
            <span className="rstate" style={{ color: STATE_COLOR[r.state] || "#aab6cc" }}>{r.state}</span>
            {r.role && <span className={`role role-${r.role}`}>{r.role === "start" ? "출발·인계" : "후속·인수"}</span>}
            <span className="rbatt">{r.battery != null ? `${r.battery}%` : "—"}</span>
          </div>
        ))}
      </section>

      <section className="card">
        <h3>CCTV</h3>
        <div className="cctv-list">
          {cams.map((c) => (
            <div key={c.id} className="cctv-row">
              <span className="cam-ic">📷</span>
              <span>{c.id.replace(/^CCTV-/, "")}</span>
              <span className="muted live">● LIVE</span>
            </div>
          ))}
        </div>
      </section>

      {alerts.length > 0 && (
        <section className="card alert-card">
          <h3>⚠ 이상 감지</h3>
          {alerts.map((a) => (
            <div key={a.id} className="alert-row">의심 인원 감지 — {a.id} ({floor})</div>
          ))}
        </section>
      )}
    </aside>
  );
}
