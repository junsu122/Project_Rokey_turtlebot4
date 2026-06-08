import { env, kioskConfig, transferPointsOnFloor } from '@/config';
import { MockRosService } from './ros';
import { MockSttService, SonioxSttService, type SttService } from './stt';
import { ClaudeLlmService, MockLlmService, type LlmService } from './llm';
import { MockNavigationService } from './navigation';
import { MockFmsService } from './fms';
import { WebSpeechTtsService } from './tts';
import type { Services } from './types';

/**
 * Composition root — the ONE place implementations are chosen.
 *
 * STT/LLM default to the REAL services (Soniox stt-rt-v4 + Claude Haiku 4.5),
 * which talk to the backend proxy (keys stay server-side). Set
 * VITE_USE_MOCKS=true for offline dev. ROS/Navigation/FMS remain mocks here —
 * they belong to the robot/server side and are plugged in separately.
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

  const fms = new MockFmsService();

  // Browser-native TTS — free/offline, no key, used only in VI mode.
  const tts = new WebSpeechTtsService();

  return { ros, stt, llm, navigation, fms, tts };
}
