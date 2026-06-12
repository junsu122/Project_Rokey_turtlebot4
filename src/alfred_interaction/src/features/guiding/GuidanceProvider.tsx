import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from 'react';
import { env, floorLevel, kioskConfig } from '@/config';
import {
  localizedFacilityName,
  type Facility,
  type NavigationSession,
} from '@/core/domain';
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

      // IF-01: tell the FMS a destination was confirmed (the server boundary).
      if (destination.poiId) {
        const request = buildEscortRequest({
          robotId: kioskConfig.robotId,
          destination: {
            poiId: destination.poiId,
            floor: floorLevel(destination.floorId),
          },
          origin: {
            floor: floorLevel(kioskConfig.currentFloorId),
            // VI(blind, 웨이크워드)는 로봇 대기 pose에서 만나고, 일반(터치 시설검색·
            // 음성검색)은 키오스크 앞(x=-7.0)에서 픽업 — profile과 같은 조건으로 분기.
            pose:
              mode === 'visually_impaired'
                ? kioskConfig.originPose
                : kioskConfig.originPoseNormal,
          },
          // VI mode (wake word) → profile blind (requirement).
          customer: defaultCustomer(
            mode === 'visually_impaired' ? 'blind' : 'normal',
            language,
          ),
        });
        requestIdRef.current = request.request_id;
        void fms.sendRequest(request);
      } else {
        requestIdRef.current = null;
        console.error('[guideTo] facility has no poiId; skipping IF-01', destination);
      }

      // Real robot connected: it owns the escort and drives the guiding screen via
      // inbound /robotN/ui_state (ESCORT_1F → … → ESCORT_COMPLETED). Show an
      // immediate "준비 중" screen for instant feedback, then let the robot's state
      // take over. No local simulation — the screen never self-completes.
      if (env.robotDrivesUi) {
        dispatch({
          type: 'ROBOT_ESCORT',
          destinationName: localizedFacilityName(destination, language),
          ratio: 0,
          preparing: true,
        });
        return;
      }

      // Offline / demo (mocks, no rosbridge): simulate the escort locally so the UI
      // is usable without a robot. The mock drives progress and auto-returns.
      const plan = navigation.planRoute(destination, kioskConfig.currentFloorId);
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
