import type { RobotStatusMessage } from '@/core/kiosk';

export type RobotStateHandler = (msg: RobotStatusMessage) => void;

/**
 * Inbound robot-state channel (IF-02). The robot (driving track) publishes its
 * current status over the ros_bridge on a per-robot topic (e.g. /robot2/ui_state);
 * the kiosk subscribes, parses the message into a RobotStatusMessage, and maps it
 * to a screen. The UI depends only on this interface — swap MockRobotStateService
 * for the real one.
 */
export interface RobotStateService {
  /** Subscribe to inbound status messages. Returns an unsubscribe function. */
  onState(handler: RobotStateHandler): () => void;
}
