import type { If01Request } from './fms/if01';

/** A fake ui_state wire message — the JSON string the robot would put on /robotN/ui_state. */
type UiStateListener = (rawJson: string) => void;
/** A fake interacting_pose message (map frame, meters). */
type PoseListener = (pose: {
  x: number;
  y: number;
  theta?: number;
  robotId?: string;
}) => void;

export interface MockRobotLinkOptions {
  /** This kiosk's robot id ('robot2' | 'robot4'). */
  robotId: string;
  /** Which floor this kiosk serves (1 | 2). */
  floor: number;
  /** Simulated escort travel time (ms) — 안내중 → 도착. */
  travelMs?: number;
  /** Delay after ESCORT before the robot "starts" (ms). */
  startMs?: number;
  /** 현위치 시작점(m) — INTERACTING 시 emit + 에스코트 보간의 출발점. */
  originPose?: readonly [number, number];
  /** poi_id → 목적지 pose(m) 조회 — 에스코트 중 현위치 dot을 목적지로 이동시킨다. */
  resolvePose?: (poiId: string) => readonly [number, number] | null;
}

/**
 * 가짜 로봇 (데모용) — rosbridge·로봇 없이 **IF-01(보냄) ↔ ui_state(받음)** 라운드트립을
 * 브라우저 안에서 시뮬레이션한다.
 *
 * 흐름: MockFmsService가 UI의 IF-01 ESCORT를 `submit()`으로 넘기면, 실제
 * escort_state_bridge_node가 발행할 법한 ui_state JSON 시퀀스
 * (ESCORT_1F → … → ESCORT_COMPLETED → PATROL)를 타이머로 `emit`한다.
 * 수신측 MockRobotStateService는 이 JSON을 **실제 수신 경로와 동일한 parseRobotStatus**로
 * 파싱하므로, "JSON 보내고 → 가짜 state JSON 받아 화면 전환"이 진짜처럼 동작한다.
 *
 * 활성화: `.env`의 `VITE_MOCK_ROBOT=true` (createServices가 이 링크를 배선).
 */
export class MockRobotLink {
  private readonly listeners = new Set<UiStateListener>();
  private readonly poseListeners = new Set<PoseListener>();
  private timers: number[] = [];

  constructor(private readonly opts: MockRobotLinkOptions) {}

  /** 수신측(MockRobotStateService) 구독. 해지 함수를 반환. */
  onUiState(fn: UiStateListener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  /** 현위치 수신측(MockRobotPoseService) 구독. 해지 함수를 반환. */
  onPose(fn: PoseListener): () => void {
    this.poseListeners.add(fn);
    return () => this.poseListeners.delete(fn);
  }

  /** MockFmsService가 UI의 IF-01 요청을 전달. ESCORT만 ui_state 시퀀스를 유발한다. */
  submit(request: If01Request): void {
    // INTERACTING(응대 시작): 현위치 pose를 즉시 emit — 실제 흐름과 동일하게
    // "interacting 보내면 바로 좌표가 온다". ui_state는 바뀌지 않음.
    if (request.request_type === 'INTERACTING') {
      const o = this.opts.originPose;
      if (o) this.emitPose(o[0], o[1]);
      return;
    }
    // CANCEL 등은 변화 없음.
    if (request.request_type !== 'ESCORT') return;
    this.runEscort(request.destination.poi_id, request.destination.floor);
  }

  /** 진행 중 시퀀스 취소(새 요청이 오면). */
  cancel(): void {
    this.timers.forEach((t) => window.clearTimeout(t));
    this.timers = [];
  }

  // ── 시퀀스 ────────────────────────────────────────────────────────────────

  private runEscort(poiId: string, destFloor: number): void {
    this.cancel();
    const start = this.opts.startMs ?? 900;
    const travel = this.opts.travelMs ?? 3500;
    const escortState = this.opts.floor === 2 ? 'ESCORT_2F' : 'ESCORT_1F';

    // 1) 로봇 출발 → "○○로 안내중" (목적지 poi_id 포함)
    this.at(start, () => this.emit(escortState, { destination: { poi_id: poiId } }));

    // 1.5) 현위치 dot 이동: origin → 목적지 pose 를 travel 동안 보간 emit(데모용).
    const from = this.opts.originPose;
    const to = this.opts.resolvePose?.(poiId) ?? null;
    if (from && to) {
      const STEPS = 12;
      for (let i = 1; i <= STEPS; i += 1) {
        const k = i / STEPS;
        const px = from[0] + (to[0] - from[0]) * k;
        const py = from[1] + (to[1] - from[1]) * k;
        this.at(start + (travel * i) / STEPS, () => this.emitPose(px, py));
      }
    }

    if (destFloor === this.opts.floor) {
      // 같은 층: 도착 → 완료 → 순찰
      // (브리지 _finish_escort 처럼 ESCORT_COMPLETED 직후 PATROL 을 연달아 보낸다)
      this.at(start + travel, () => {
        this.emit('ESCORT_COMPLETED');
        this.emit('PATROL');
      });
    } else {
      // 다른 층(환승): 이 키오스크는 "N층으로 이동" 안내까지 보여주고, 핸드오프 후 순찰 복귀.
      const finished = this.opts.floor === 2 ? 'ESCORT_2F_FINISHED' : 'ESCORT_1F_FINISHED';
      const targetFloor = this.opts.floor === 2 ? 1 : 2;
      this.at(start + travel, () => this.emit(finished, { target_floor: targetFloor }));
      this.at(start + travel + 4000, () => this.emit('PATROL'));
    }
  }

  /** ui_state 한 건을 JSON 문자열로 만들어 구독자에게 전달(가짜 wire 메시지). */
  private emit(state: string, extra?: Record<string, unknown>): void {
    const payload = { state, robot_id: this.opts.robotId, ...(extra ?? {}) };
    const raw = JSON.stringify(payload);
    for (const fn of this.listeners) fn(raw);
  }

  /** interacting_pose 한 건을 구독자(MockRobotPoseService)에게 전달. */
  private emitPose(x: number, y: number, theta = 0): void {
    for (const fn of this.poseListeners) {
      fn({ x, y, theta, robotId: this.opts.robotId });
    }
  }

  private at(ms: number, fn: () => void): void {
    this.timers.push(window.setTimeout(fn, ms));
  }
}
