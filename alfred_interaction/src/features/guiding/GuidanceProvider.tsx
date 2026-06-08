import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from 'react';
import { floorLevel, kioskConfig } from '@/config';
import type { Facility, NavigationSession } from '@/core/domain';
import { useLanguage } from '@/core/i18n';
import { useKioskDispatch, useKioskState } from '@/core/kiosk';
import {
  buildCancelRequest,
  buildEscortRequest,
  defaultCustomer,
  useServices,
  type NavigationHandle,
} from '@/services';

interface GuidanceControls {
  /** Plan + begin escorting to a facility, moving the kiosk into 'guiding'. */
  guideTo: (destination: Facility) => void;
  /** Abort the current escort and return to patrol. */
  cancelGuidance: () => void;
}

const GuidanceContext = createContext<GuidanceControls | null>(null);

/**
 * Owns the live escort: bridges the NavigationService to the kiosk state machine
 * and auto-returns to patrol on arrival (requirement #10). Mounted once at the
 * app root so navigation survives the map/voice → guiding screen switch.
 */
export function GuidanceProvider({ children }: { children: ReactNode }) {
  const dispatch = useKioskDispatch();
  const { mode } = useKioskState();
  const { language } = useLanguage();
  const { navigation, fms } = useServices();
  const handleRef = useRef<NavigationHandle | null>(null);
  const arrivedTimerRef = useRef<number | null>(null);
  /** request_id of the in-flight IF-01, so we can CANCEL the right one. */
  const requestIdRef = useRef<string | null>(null);

  const clearArrivedTimer = useCallback(() => {
    if (arrivedTimerRef.current !== null) {
      window.clearTimeout(arrivedTimerRef.current);
      arrivedTimerRef.current = null;
    }
  }, []);

  const guideTo = useCallback(
    (destination: Facility) => {
      handleRef.current?.cancel();
      clearArrivedTimer();

      const plan = navigation.planRoute(destination, kioskConfig.currentFloorId);

      // IF-01: tell the FMS a destination was confirmed (the server boundary).
      // The local navigation below only drives the on-screen escort animation.
      if (destination.poiId) {
        const request = buildEscortRequest({
          robotId: kioskConfig.robotId,
          destination: {
            poiId: destination.poiId,
            floor: floorLevel(destination.floorId),
          },
          origin: {
            floor: floorLevel(kioskConfig.currentFloorId),
            pose: kioskConfig.originPose,
          },
          // VI mode (wake word) → profile VISUALLY_IMPAIRED (requirement).
          customer: defaultCustomer(
            mode === 'visually_impaired' ? 'VISUALLY_IMPAIRED' : 'GENERAL',
            language,
          ),
        });
        requestIdRef.current = request.request_id;
        void fms.sendRequest(request);
      } else {
        requestIdRef.current = null;
        console.error('[guideTo] facility has no poiId; skipping IF-01', destination);
      }

      const session: NavigationSession = {
        plan,
        progress: { phase: 'starting', ratio: 0 },
      };
      dispatch({ type: 'START_GUIDING', session });

      handleRef.current = navigation.start(plan, {
        onProgress: (progress) => {
          dispatch({ type: 'UPDATE_PROGRESS', progress });
          if (progress.phase === 'arrived') {
            clearArrivedTimer();
            arrivedTimerRef.current = window.setTimeout(() => {
              handleRef.current = null;
              requestIdRef.current = null;
              dispatch({ type: 'END_GUIDING' });
            }, kioskConfig.arrivedHoldMs);
          }
        },
      });
    },
    [navigation, fms, dispatch, clearArrivedTimer, mode, language],
  );

  const cancelGuidance = useCallback(() => {
    handleRef.current?.cancel();
    handleRef.current = null;
    clearArrivedTimer();
    // IF-01 CANCEL: let the FMS unwind the mission (정의서 §7).
    if (requestIdRef.current) {
      void fms.sendRequest(
        buildCancelRequest(kioskConfig.robotId, requestIdRef.current),
      );
      requestIdRef.current = null;
    }
    dispatch({ type: 'END_GUIDING' });
  }, [fms, dispatch, clearArrivedTimer]);

  useEffect(() => {
    return () => {
      handleRef.current?.cancel();
      clearArrivedTimer();
    };
  }, [clearArrivedTimer]);

  return (
    <GuidanceContext.Provider value={{ guideTo, cancelGuidance }}>
      {children}
    </GuidanceContext.Provider>
  );
}

export function useGuidance(): GuidanceControls {
  const ctx = useContext(GuidanceContext);
  if (!ctx) {
    throw new Error('useGuidance must be used within <GuidanceProvider>');
  }
  return ctx;
}
