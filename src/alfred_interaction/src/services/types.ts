import type { RosService } from './ros';
import type { SttService } from './stt';
import type { LlmService } from './llm';
import type { NavigationService } from './navigation';
import type { FmsService } from './fms';
import type { DetectionService } from './detection';
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
  /** Text-to-speech (VI mode + emergency announcements). Browser-native, no key. */
  tts: TtsService;
}
