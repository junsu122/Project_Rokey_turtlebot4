import { parseDetectionLabel, type DetectionType } from '@/core/domain';
import type { RosBridgeClient } from '../ros';
import type { DetectionHandler, DetectionService } from './DetectionService';

const TAG = '[detection]';

/**
 * Real inbound-detection channel over the ros_bridge. Subscribes to the YOLO
 * detection topic(s) on the robot/laptop graph and maps each message to a
 * DetectionType. Shares the SAME RosBridgeClient as the FMS channel (one socket
 * to the Turtlebot4 laptop).
 */
export class RosBridgeDetectionService implements DetectionService {
  constructor(
    private readonly bridge: RosBridgeClient,
    /** One or more topics carrying detections (e.g. ['/detection']). */
    private readonly topics: string[],
  ) {}

  onDetection(handler: DetectionHandler): () => void {
    for (const topic of this.topics) {
      this.bridge.subscribe(topic, (msg) => {
        const detection = extractDetection(topic, msg);
        if (detection) {
          console.info(`${TAG} ${detection} ← ${topic}`, msg);
          handler(detection);
        } else {
          console.debug(`${TAG} ignored message on ${topic}`, msg);
        }
      });
    }
    return () => {
      for (const topic of this.topics) this.bridge.unsubscribe(topic);
    };
  }
}

/**
 * Pull a DetectionType out of whatever the robot publishes. Handles the common
 * shapes so the Vision track can use any of them:
 *  - std_msgs/String:  { data: 'FIRE' }  or  { data: '{"type":"FIRE"}' }
 *  - custom message:   { type } / { event_type } / { label } / { class }
 *  - bare string
 *  - the topic name itself (e.g. /detection/fire) as a fallback
 *
 * ★ This is the one place to adjust when the real detection contract is fixed.
 */
function extractDetection(topic: string, msg: unknown): DetectionType | null {
  return parseDetectionLabel(labelFromMessage(msg)) ?? parseDetectionLabel(topic);
}

function labelFromMessage(msg: unknown): string {
  if (typeof msg === 'string') return msg;
  if (msg && typeof msg === 'object') {
    const o = msg as Record<string, unknown>;
    const direct = o.type ?? o.event_type ?? o.label ?? o.class ?? o.detection;
    if (typeof direct === 'string') return direct;
    if (typeof o.data === 'string') {
      try {
        const inner = JSON.parse(o.data) as Record<string, unknown>;
        const t = inner.type ?? inner.event_type ?? inner.label ?? inner.class;
        if (typeof t === 'string') return t;
      } catch {
        /* not JSON — fall through to the raw string */
      }
      return o.data;
    }
  }
  return '';
}
