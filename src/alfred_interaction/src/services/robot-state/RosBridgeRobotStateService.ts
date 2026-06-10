import type { RobotStatusMessage } from '@/core/kiosk';
import type { RosBridgeClient } from '../ros';
import type { RobotStateHandler, RobotStateService } from './RobotStateService';

const TAG = '[robot-state]';

/**
 * Real inbound robot-state channel over the ros_bridge. Subscribes to this
 * kiosk's per-robot status topic (e.g. /robot2/ui_state) and parses whatever the
 * robot publishes into a RobotStatusMessage (see `parseRobotStatus`). Shares the
 * SAME RosBridgeClient socket as FMS/detection.
 */
export class RosBridgeRobotStateService implements RobotStateService {
  constructor(
    private readonly bridge: RosBridgeClient,
    private readonly topic: string,
  ) {}

  onState(handler: RobotStateHandler): () => void {
    this.bridge.subscribe(this.topic, (raw) => {
      const msg = parseRobotStatus(raw);
      if (msg) {
        console.info(`${TAG} ${msg.state} ← ${this.topic}`, msg);
        handler(msg);
      } else {
        console.debug(`${TAG} ignored message on ${this.topic}`, raw);
      }
    });
    return () => this.bridge.unsubscribe(this.topic);
  }
}

/**
 * Normalize whatever the robot publishes into a RobotStatusMessage. Handles:
 *  - custom msg (fields directly):  { state, robot_id, destination, target_floor, battery, progress }
 *  - std_msgs/String (label):       { data: 'ESCORT_1F' }
 *  - std_msgs/String (JSON):        { data: '{"state":"ESCORT_1F","destination":{"poi_id":"WC"}}' }
 *  - bare string / JSON string
 * Accepts snake_case (ROS convention) and camelCase keys. Returns null if there's
 * no usable `state`.
 */
function parseRobotStatus(raw: unknown): RobotStatusMessage | null {
  const src = toSource(raw);
  if (!src) return null;
  const state = str(src.state ?? src.status);
  if (!state) return null;
  return {
    state,
    robotId: str(src.robot_id ?? src.robotId) || undefined,
    destination: parseDestination(src.destination),
    targetFloor: num(src.target_floor ?? src.targetFloor),
    battery: num(src.battery),
    progress: num(src.progress),
    timestamp: str(src.timestamp) || undefined,
  };
}

function toSource(raw: unknown): Record<string, unknown> | null {
  if (typeof raw === 'string') {
    const s = raw.trim();
    return s.startsWith('{') ? tryJson(s) : { state: s };
  }
  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>;
    if (typeof o.data === 'string') {
      const d = o.data.trim();
      return d.startsWith('{') ? tryJson(d) : { state: d };
    }
    return o; // custom message with structured fields
  }
  return null;
}

function tryJson(text: string): Record<string, unknown> | null {
  try {
    const v = JSON.parse(text);
    return v && typeof v === 'object' ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function parseDestination(
  raw: unknown,
): { poiId?: string; name?: string } | undefined {
  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>;
    const poiId = str(o.poi_id ?? o.poiId) || undefined;
    const name = str(o.name) || undefined;
    if (poiId || name) return { poiId, name };
  }
  return undefined;
}

function str(v: unknown): string {
  return typeof v === 'string' ? v.trim() : '';
}

function num(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) {
    return Number(v);
  }
  return undefined;
}
