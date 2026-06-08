import type { RosService } from './ros';
import type { SttService } from './stt';
import type { LlmService } from './llm';
import type { NavigationService } from './navigation';
import type { FmsService } from './fms';
import type { TtsService } from './tts';

/** The full set of services the UI consumes. Provide real impls to go live. */
export interface Services {
  ros: RosService;
  stt: SttService;
  llm: LlmService;
  navigation: NavigationService;
  fms: FmsService;
  /** Text-to-speech (visually-impaired mode). Browser-native, no key. */
  tts: TtsService;
}
