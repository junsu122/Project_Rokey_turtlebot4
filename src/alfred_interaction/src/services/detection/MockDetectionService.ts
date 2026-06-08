import type { DetectionHandler, DetectionService } from './DetectionService';

/**
 * Offline stand-in (no robot / no rosbridge). Emits nothing on its own — alerts
 * can still be raised manually for testing via the AlertsProvider window hook
 * (`window.alfredAlert('FIRE')`). Swap for RosBridgeDetectionService to go live.
 */
export class MockDetectionService implements DetectionService {
  onDetection(_handler: DetectionHandler): () => void {
    return () => {};
  }
}
