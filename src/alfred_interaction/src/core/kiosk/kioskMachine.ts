import type { KioskEvent, KioskState } from './types';

export const initialKioskState: KioskState = {
  screen: 'patrol',
  mode: 'general',
  staffCallActive: false,
  session: null,
  alert: null,
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

    default:
      return state;
  }
}
