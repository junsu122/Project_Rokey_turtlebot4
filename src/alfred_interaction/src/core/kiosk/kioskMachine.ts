import type { KioskEvent, KioskState } from './types';

export const initialKioskState: KioskState = {
  screen: 'patrol',
  mode: 'general',
  staffCallActive: false,
  session: null,
  alert: null,
  waiting: null,
  escort: null,
  chargeBattery: null,
};

/**
 * Pure transition function for the kiosk. Invalid transitions are no-ops, which
 * keeps the UI robust against stray events (e.g. a late progress update).
 *
 *   patrol ──WAKE──▶ home ──OPEN_MAP──▶ map ─┐
 *                     │  ──OPEN_VOICE─▶ voice ┼─START_GUIDING─▶ guiding
 *                     ▲  ◀───GO_HOME──────────┘                   │
 *                     └──────────────── END_GUIDING / IDLE ───────┘ ▶ patrol
 */
export function kioskReducer(state: KioskState, event: KioskEvent): KioskState {
  switch (event.type) {
    case 'WAKE':
      return state.screen === 'patrol' ? { ...state, screen: 'home' } : state;

    case 'WAKE_VOICE':
      // Wake word during patrol → jump straight to voice in VI (TTS) mode.
      return state.screen === 'patrol'
        ? { ...state, screen: 'voice', mode: 'visually_impaired' }
        : state;

    case 'OPEN_MAP':
      return state.screen === 'home' ? { ...state, screen: 'map' } : state;

    case 'OPEN_VOICE':
      return state.screen === 'home' ? { ...state, screen: 'voice' } : state;

    case 'GO_HOME':
      return state.screen === 'map' || state.screen === 'voice'
        ? { ...state, screen: 'home' }
        : state;

    case 'START_GUIDING':
      return { ...state, screen: 'guiding', session: event.session };

    case 'UPDATE_PROGRESS':
      return state.session
        ? {
            ...state,
            session: { ...state.session, progress: event.progress },
          }
        : state;

    case 'END_GUIDING':
      // Requirement #10: escort finished → back to patrol.
      return { ...initialKioskState };

    case 'IDLE_TIMEOUT':
      // Never interrupt an active escort.
      return state.screen === 'guiding' ? state : { ...initialKioskState };

    case 'OPEN_STAFF_CALL':
      return { ...state, staffCallActive: true };

    case 'CLOSE_STAFF_CALL':
      return { ...state, staffCallActive: false };

    case 'DETECTION':
      // Requirement ver03: a YOLO emergency takes over the whole kiosk from any
      // screen. Drop any staff popup so nothing covers the alert.
      return {
        ...state,
        screen: 'alert',
        alert: event.detection,
        staffCallActive: false,
      };

    case 'CLEAR_ALERT':
      // Staff dismissed the alert → back to a clean patrol.
      return state.screen === 'alert' ? { ...initialKioskState } : state;

    case 'ENTER_CHARGING':
      // Robot docked/charging takes over with a clean state (not during an alert).
      return state.screen === 'alert'
        ? state
        : {
            ...initialKioskState,
            screen: 'charging',
            chargeBattery: event.battery ?? null,
          };

    case 'ENTER_WAITING':
      // Robot waiting / cross-floor handoff (keeps mode for VI announcements).
      return state.screen === 'alert'
        ? state
        : {
            ...state,
            screen: 'waiting',
            waiting: event.info,
            session: null,
            escort: null,
          };

    case 'ROBOT_ESCORT':
      // Robot-driven escort → guiding. A local session (user picked on the kiosk)
      // takes priority in the screen, so we only fill `escort` for the no-session
      // case; either way move to guiding.
      return state.screen === 'alert'
        ? state
        : {
            ...state,
            screen: 'guiding',
            escort: {
              destinationName: event.destinationName ?? null,
              ratio: event.ratio ?? 0,
              preparing: event.preparing ?? false,
              arrived: false,
            },
          };

    case 'ROBOT_ARRIVED':
      // Robot reported final arrival (ESCORT_COMPLETED) → hold a "도착했어요!" screen.
      // A timer in RobotStateProvider returns to patrol; the trailing PATROL is
      // ignored meanwhile (see EXIT_ROBOT_SCREEN). Never overrides an alert.
      return state.screen === 'alert'
        ? state
        : {
            ...state,
            screen: 'guiding',
            session: null,
            escort: {
              destinationName: state.escort?.destinationName ?? null,
              ratio: 1,
              preparing: false,
              arrived: true,
            },
          };

    case 'EXIT_ROBOT_SCREEN':
      // Robot back to PATROL → leave robot-driven screens only (never a local escort,
      // and never while the "도착했어요!" arrival screen is still holding). A lingering
      // alert is also cleared when the robot resumes patrol.
      return state.screen === 'charging' ||
        state.screen === 'waiting' ||
        state.screen === 'alert' ||
        (state.screen === 'guiding' &&
          !!state.escort &&
          !state.session &&
          !state.escort.arrived)
        ? { ...initialKioskState }
        : state;

    default:
      return state;
  }
}
