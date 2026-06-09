import { env, kioskConfig, transferPointsOnFloor } from '@/config';
import { MockRosService, RosBridgeClient } from './ros';
import { MockSttService, SonioxSttService, type SttService } from './stt';
import { ClaudeLlmService, MockLlmService, type LlmService } from './llm';
import { MockNavigationService } from './navigation';
import { MockFmsService, RosBridgeFmsService, type FmsService } from './fms';
import {
  MockDetectionService,
  RosBridgeDetectionService,
  type DetectionService,
} from './detection';
import { WebSpeechTtsService } from './tts';
import type { Services } from './types';

/**
 * Composition root — the ONE place implementations are chosen.
 *
 * STT/LLM default to the REAL services (Soniox stt-rt-v4 + Claude Haiku 4.5),
 * which talk to the backend proxy (keys stay server-side). Set
 * VITE_USE_MOCKS=true for offline dev. The FMS channel goes live over the
 * ros_bridge when VITE_ROSBRIDGE_HOST is set (publishes IF-01 to /information),
 * else it logs the wire frame. ROS motion / Navigation stay mocks here — they
 * belong to the robot side and are plugged in separately.
 */
export function createDefaultServices(): Services {
  const ros = new MockRosService();
  void ros.connect();

  const stt: SttService = env.useMocks
    ? new MockSttService()
    : new SonioxSttService({
        temporaryKeyEndpoint: `${env.apiBase}/soniox/temporary-api-key`,
        model: env.sonioxModel,
        gateDb: env.micGateDb,
        gateDebug: env.micGateDebug,
      });

  const llm: LlmService = env.useMocks
    ? new MockLlmService()
    : new ClaudeLlmService({ endpoint: `${env.apiBase}/llm/understand` });

  const navigation = new MockNavigationService({
    ros,
    getTransferPoints: transferPointsOnFloor,
    travelMs: kioskConfig.simulatedTravelMs,
    handoffMs: kioskConfig.simulatedHandoffMs,
  });

  // ros_bridge channels to the Turtlebot4 laptop, over ONE shared WebSocket:
  //   • FMS (IF-01)  — kiosk → /information (publish)
  //   • Detections   — robot → /detection   (subscribe, requirement ver03)
  // With no URL (or mocks forced), both fall back to console/no-op so the UI
  // runs offline. See env.rosbridgeUrl / .env.
  let fms: FmsService;
  let detection: DetectionService;
  if (!env.useMocks && env.rosbridgeUrl) {
    const bridge = new RosBridgeClient({ url: env.rosbridgeUrl });
    bridge.connect();
    // Advertise the type BEFORE any publish — rosbridge rejects a publish to a
    // topic whose message type it can't infer ("Cannot infer topic type").
    if (env.rosInfoMsgType) bridge.advertise(env.rosInfoTopic, env.rosInfoMsgType);
    fms = new RosBridgeFmsService(bridge, env.rosInfoTopic, env.rosInfoMsgType);
    detection = new RosBridgeDetectionService(bridge, env.detectionTopics);
  } else {
    fms = new MockFmsService(env.rosInfoTopic, env.rosInfoMsgType);
    detection = new MockDetectionService();
  }

  // Browser-native TTS — free/offline, no key (VI mode + emergency alerts).
  const tts = new WebSpeechTtsService();

  return { ros, stt, llm, navigation, fms, detection, tts };
}
