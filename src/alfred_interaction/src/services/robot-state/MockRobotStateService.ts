import type { MockRobotLink } from '../MockRobotLink';
import { parseRobotStatus } from './RosBridgeRobotStateService';
import type { RobotStateHandler, RobotStateService } from './RobotStateService';

const TAG = '[MockRobotState]';

/**
 * Offline stand-in (no robot / no rosbridge).
 *
 * - link 없음(기본): 스스로는 아무것도 보내지 않음 — 상태는 RobotStateProvider의 window
 *   훅(`window.alfredRobotStatus('DOCKING')`)으로 수동 주입 가능.
 * - link 있음(VITE_MOCK_ROBOT): 가짜 로봇이 emit한 ui_state JSON을 **실제 수신 경로와 동일한
 *   parseRobotStatus**로 파싱해 화면으로 흘려보낸다 → rosbridge 없이 전체 흐름 시연.
 *
 * Swap for RosBridgeRobotStateService to go live.
 */
export class MockRobotStateService implements RobotStateService {
  constructor(private readonly link?: MockRobotLink) {}

  onState(handler: RobotStateHandler): () => void {
    if (!this.link) return () => {};
    return this.link.onUiState((raw) => {
      const msg = parseRobotStatus(raw); // 가짜 JSON도 실제와 똑같이 파싱
      if (msg) {
        console.info(`${TAG} ${msg.state} ← (mock ui_state)`, msg);
        handler(msg);
      }
    });
  }
}
