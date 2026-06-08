/**
 * ROS bridge contract — THE server boundary for robot motion.
 *
 * In production this is implemented with roslibjs over rosbridge_websocket:
 * `publishGoal` → a Nav2 / move_base goal, `requestHandoff` → a topic the other
 * floor's robot subscribes to (requirement #6). The UI only ever depends on this
 * interface, never on a concrete transport — swap MockRosService for a real one.
 */
export interface RosGoal {
  facilityId: string;
  facilityName: string;
  floorId: string;
  /** Target pose in the floor's map frame (here: blueprint units). */
  x: number;
  y: number;
}

export interface RosConnectionStatus {
  connected: boolean;
  url?: string;
  lastError?: string;
}

export interface RosService {
  connect(): Promise<void>;
  disconnect(): void;
  getStatus(): RosConnectionStatus;

  /** Command this robot to drive to a goal pose. */
  publishGoal(goal: RosGoal): Promise<void>;

  /** Cancel the in-flight goal. */
  cancelGoal(): Promise<void>;

  /**
   * Ask the OTHER floor's robot to stage at the landing and continue the escort
   * to `goal` (the cross-floor handoff in requirement #6).
   */
  requestHandoff(toFloorId: string, goal: RosGoal): Promise<void>;
}
