/** Service layer barrel. */
export type { Services } from './types';
export { ServiceProvider, useServices } from './ServiceProvider';
export { createDefaultServices } from './createServices';

export type { RosService, RosGoal, RosConnectionStatus } from './ros';
export { RosBridgeClient, rosPublish } from './ros';
export type {
  RosBridgeOptions,
  RosBridgeStatus,
  RosPublishEnvelope,
} from './ros';
export type {
  SttService,
  SttSession,
  SttResult,
  SttHandlers,
  SttStartOptions,
} from './stt';
export type {
  LlmService,
  VoiceUnderstanding,
  VoiceIntent,
  LlmUnderstandOptions,
} from './llm';
export type {
  NavigationService,
  NavigationHandle,
  NavigationHandlers,
} from './navigation';
export type { FmsService } from './fms';
export { MockFmsService, RosBridgeFmsService } from './fms';
export type { DetectionService, DetectionHandler } from './detection';
export { MockDetectionService, RosBridgeDetectionService } from './detection';
export type { RobotStateService, RobotStateHandler } from './robot-state';
export { MockRobotStateService, RosBridgeRobotStateService } from './robot-state';
export type { TtsService, TtsSpeakOptions } from './tts';
export { WebSpeechTtsService, MockTtsService } from './tts';
export { useSpeak } from './useSpeak';
export {
  IF_VERSION,
  buildEscortRequest,
  buildCancelRequest,
  buildInteractingRequest,
  defaultCustomer,
} from './fms';
export type {
  If01Request,
  If01EscortRequest,
  If01CancelRequest,
  If01InteractingRequest,
  If01Customer,
  If01Origin,
  CustomerProfile,
} from './fms';
