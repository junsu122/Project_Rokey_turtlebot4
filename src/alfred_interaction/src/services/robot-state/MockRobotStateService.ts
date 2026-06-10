import type { RobotStateHandler, RobotStateService } from './RobotStateService';

/**
 * Offline stand-in (no robot / no rosbridge). Emits nothing on its own — statuses
 * can still be driven manually for testing via the RobotStateProvider window hook
 * (`window.alfredRobotStatus('DOCKING')`). Swap for RosBridgeRobotStateService to
 * go live.
 */
export class MockRobotStateService implements RobotStateService {
  onState(_handler: RobotStateHandler): () => void {
    return () => {};
  }
}
