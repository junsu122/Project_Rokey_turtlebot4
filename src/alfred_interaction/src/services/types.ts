import type { RosService } from './ros';
import type { SttService } from './stt';
import type { LlmService } from './llm';
import type { NavigationService } from './navigation';
import type { FmsService } from './fms';
import type { DetectionService } from './detection';
import type { RobotStateService } from './robot-state';
import type { RobotPoseService } from './robot-pose';
import type { TtsService } from './tts';

/** The full set of services the UI consumes. Provide real impls to go live. */
export interface Services {
  ros: RosService;
  stt: SttService;
  llm: LlmService;
  navigation: NavigationService;
  fms: FmsService;
  /** Inbound YOLO emergency detections (FIRE/INJURED/SUSPICIOUS) → alerts. */
  detection: DetectionService;
  /** Inbound robot status (IF-02) → screen (charging/waiting/patrol/...). */
  robotState: RobotStateService;
  /** Inbound robot live pose (m) → map "현위치" dot. */
  robotPose: RobotPoseService;
  /** Text-to-speech (VI mode + emergency announcements). Browser-native, no key. */
  tts: TtsService;
}
