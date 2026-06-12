import type { RosBridgeClient } from '../ros';
import type {
  RobotPose,
  RobotPoseHandler,
  RobotPoseService,
} from './RobotPoseService';

const TAG = '[robot-pose]';

/**
 * Real inbound robot-pose channel over the ros_bridge. Subscribes to this
 * kiosk's per-robot pose topic (e.g. /robot2/interacting_pose) and parses the
 * message into a RobotPose. Shares the SAME RosBridgeClient socket as FMS /
 * detection / robot-state.
 *
 * Wire message (rosbridge `msg`): { robot_id, x, y, theta }  — meters / radians.
 */
export class RosBridgeRobotPoseService implements RobotPoseService {
  constructor(
    private readonly bridge: RosBridgeClient,
    private readonly topic: string,
  ) {}

  onPose(handler: RobotPoseHandler): () => void {
    this.bridge.subscribe(this.topic, (raw) => {
      const pose = parseRobotPose(raw);
      if (pose) {
        console.debug(`${TAG} (${pose.x.toFixed(2)}, ${pose.y.toFixed(2)}) ← ${this.topic}`);
        handler(pose);
      }
    });
    return () => this.bridge.unsubscribe(this.topic);
  }
}

/**
 * Normalize whatever the robot publishes into a RobotPose. Handles the structured
 * message ({x,y,theta,robot_id}) and a std_msgs/String JSON ({data:'{...}'}).
 * Returns null without a usable x/y.
 */
export function parseRobotPose(raw: unknown): RobotPose | null {
  const src = toObject(raw);
  if (!src) return null;
  const x = num(src.x);
  const y = num(src.y);
  if (x === undefined || y === undefined) return null;
  return {
    x,
    y,
    theta: num(src.theta),
    robotId: str(src.robot_id ?? src.robotId) || undefined,
  };
}

function toObject(raw: unknown): Record<string, unknown> | null {
  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>;
    if (typeof o.data === 'string') return tryJson(o.data); // std_msgs/String JSON
    return o; // structured message
  }
  if (typeof raw === 'string') return tryJson(raw);
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

function num(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) {
    return Number(v);
  }
  return undefined;
}

function str(v: unknown): string {
  return typeof v === 'string' ? v.trim() : '';
}
