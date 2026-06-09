import { useEffect, type ReactNode } from 'react';
import type { DetectionType } from '@/core/domain';
import { useKioskDispatch } from '@/core/kiosk';
import { useServices } from '@/services';

/**
 * Bridges inbound YOLO detections to the kiosk state machine: subscribes to the
 * DetectionService and raises a full-screen alert (requirement ver03). Mounted
 * once at the app root.
 *
 * For the feature owner — to plug in the real robot, only two seams matter:
 *   1. the ROS topic(s):  VITE_DETECTION_TOPIC  (.env)
 *   2. the message → type mapping:  services/detection/RosBridgeDetectionService
 *
 * Manual trigger (no robot needed) from the browser console:
 *   window.alfredAlert('FIRE' | 'INJURED' | 'SUSPICIOUS')
 *   window.alfredClearAlert()
 */
export function AlertsProvider({ children }: { children: ReactNode }) {
  const dispatch = useKioskDispatch();
  const { detection } = useServices();

  // Real source: ROS bridge detections → alert.
  useEffect(() => {
    return detection.onDetection((type) =>
      dispatch({ type: 'DETECTION', detection: type }),
    );
  }, [detection, dispatch]);

  // Manual test hooks on window (handy for demos / the feature owner).
  useEffect(() => {
    const w = window as unknown as {
      alfredAlert?: (t: DetectionType) => void;
      alfredClearAlert?: () => void;
    };
    w.alfredAlert = (t) => dispatch({ type: 'DETECTION', detection: t });
    w.alfredClearAlert = () => dispatch({ type: 'CLEAR_ALERT' });
    console.info(
      "[alerts] test from console: window.alfredAlert('FIRE'|'INJURED'|'SUSPICIOUS'); window.alfredClearAlert()",
    );
    return () => {
      delete w.alfredAlert;
      delete w.alfredClearAlert;
    };
  }, [dispatch]);

  return <>{children}</>;
}
