/** Robot live pose in the map frame (meters), from /robotN/interacting_pose. */
export interface RobotPose {
  /** Map-frame x (meters). */
  x: number;
  /** Map-frame y (meters). */
  y: number;
  /** Heading (radians) — optional, for a direction indicator. */
  theta?: number;
  /** Which robot reported it (robot2 / robot4). */
  robotId?: string;
}

export type RobotPoseHandler = (pose: RobotPose) => void;

/**
 * Inbound robot-pose channel. The robot (driving track) publishes its live
 * map-frame pose on a per-robot topic (e.g. /robot2/interacting_pose, sent right
 * after an INTERACTING request); the kiosk subscribes and renders a live "현위치"
 * dot on the facility map. The UI depends only on this interface — swap
 * MockRobotPoseService for the real one.
 */
export interface RobotPoseService {
  /** Subscribe to inbound pose messages. Returns an unsubscribe function. */
  onPose(handler: RobotPoseHandler): () => void;
}
