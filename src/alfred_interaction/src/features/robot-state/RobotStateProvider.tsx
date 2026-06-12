import { useCallback, useEffect, useRef, type ReactNode } from 'react';
import { getFacilityByPoiId, kioskConfig } from '@/config';
import { localizedFacilityName } from '@/core/domain';
import { useLanguage, type Language } from '@/core/i18n';
import {
  robotStatusToEvent,
  useKioskDispatch,
  type RobotStatus,
  type RobotStatusMessage,
} from '@/core/kiosk';
import { useServices } from '@/services';

/**
 * Bridges inbound robot status (IF-02 over ros_bridge, e.g. /robot2/ui_state) to
 * the kiosk: subscribes to the RobotStateService and dispatches the mapped event
 * (charging / waiting / patrol / escort / …). Mounted once at the app root.
 *
 * ESCORT_1F/2F is handled here (not in robotStatusToEvent) because it needs the
 * destination NAME resolved from `poi_id` + the active language.
 *
 * For the driving track — two seams:
 *   1. topic:            VITE_ROBOT_STATE_TOPIC (.env) — else /<robotId>/ui_state
 *   2. status → screen:  core/kiosk/robotStatus.ts
 *
 * Manual trigger (no robot) from the console:
 *   window.alfredRobotStatus('DOCKING')
 *   window.alfredRobotStatus({ state: 'ESCORT_1F', destination: { poi_id: 'WC' }, progress: 0.5 })
 */
export function RobotStateProvider({ children }: { children: ReactNode }) {
  const dispatch = useKioskDispatch();
  const { language } = useLanguage();
  const { robotState } = useServices();
  /** Holds the "도착했어요!" screen, then returns to patrol (ESCORT_COMPLETED). */
  const arrivedTimerRef = useRef<number | null>(null);
  const clearArrivedTimer = useCallback(() => {
    if (arrivedTimerRef.current !== null) {
      window.clearTimeout(arrivedTimerRef.current);
      arrivedTimerRef.current = null;
    }
  }, []);

  const handleStatus = useCallback(
    (msg: RobotStatusMessage) => {
      if (msg.state === 'ESCORT_1F' || msg.state === 'ESCORT_2F') {
        clearArrivedTimer(); // a fresh escort supersedes any pending arrival hold
        dispatch({
          type: 'ROBOT_ESCORT',
          destinationName: resolveDestinationName(msg.destination, language),
          ratio: msg.progress,
          // The robot reports it's actively escorting → leave "preparing".
          preparing: false,
        });
        return;
      }
      // ESCORT_COMPLETED → show "도착했어요!" briefly, then return to patrol. The
      // bridge publishes PATROL right after; it's ignored during this hold.
      if (msg.state === 'ESCORT_COMPLETED') {
        dispatch({ type: 'ROBOT_ARRIVED' });
        clearArrivedTimer();
        arrivedTimerRef.current = window.setTimeout(
          () => dispatch({ type: 'END_GUIDING' }),
          kioskConfig.arrivedHoldMs,
        );
        return;
      }
      const event = robotStatusToEvent(msg);
      if (event) dispatch(event);
    },
    [dispatch, language, clearArrivedTimer],
  );

  // Real source: ros_bridge robot status → screen.
  useEffect(() => robotState.onState(handleStatus), [robotState, handleStatus]);

  // Clear the arrival-hold timer on unmount.
  useEffect(() => () => clearArrivedTimer(), [clearArrivedTimer]);

  // Manual test hook on window. Accepts a bare state string or a full message.
  useEffect(() => {
    const w = window as unknown as {
      alfredRobotStatus?: (s: RobotStatus | RobotStatusMessage) => void;
    };
    w.alfredRobotStatus = (s) =>
      handleStatus(typeof s === 'string' ? { state: s } : s);
    console.info(
      "[robot-status] test: window.alfredRobotStatus('DOCKING'|'WAITING_1F'|'ESCORT_1F_FINISHED'|'ESCORT_COMPLETED'|'PATROL') " +
        "or window.alfredRobotStatus({state:'ESCORT_1F',destination:{poi_id:'WC'},progress:0.5})",
    );
    return () => {
      delete w.alfredRobotStatus;
    };
  }, [handleStatus]);

  return <>{children}</>;
}

/** poi_id → localized facility name; else the robot-provided name; else null. */
function resolveDestinationName(
  destination: RobotStatusMessage['destination'],
  language: Language,
): string | null {
  if (!destination) return null;
  if (destination.poiId) {
    const facility = getFacilityByPoiId(destination.poiId);
    if (facility) return localizedFacilityName(facility, language);
  }
  return destination.name ?? null;
}
