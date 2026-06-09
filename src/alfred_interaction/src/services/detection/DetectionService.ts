import type { DetectionType } from '@/core/domain';

export type DetectionHandler = (detection: DetectionType) => void;

/**
 * Inbound emergency-detection channel (requirement ver03) — the REVERSE of the
 * FMS request channel. The robot's vision (YOLO) publishes FIRE / INJURED /
 * SUSPICIOUS over the ROS bridge; the kiosk subscribes and raises a full-screen
 * alert. The UI depends only on this interface — swap MockDetectionService for
 * the real RosBridgeDetectionService (same shared bridge as the FMS channel).
 */
export interface DetectionService {
  /** Subscribe to incoming detections. Returns an unsubscribe function. */
  onDetection(handler: DetectionHandler): () => void;
}
