import type {
  DetectionType,
  NavigationProgress,
  NavigationSession,
} from '@/core/domain';

/** The top-level kiosk screens (the finite states). */
export type KioskScreen =
  | 'patrol'
  | 'home'
  | 'map'
  | 'voice'
  | 'guiding'
  | 'alert'
  | 'charging' // robot docked / charging (DOCKING / UNDOCKING)
  | 'waiting'; // robot waiting for the user / cross-floor handoff

/**
 * Context for the 'waiting' screen (robot-state driven, IF-02). `waiting` = the
 * robot is parked waiting for the user; `transfer` = this floor's escort is done
 * and the user should move to `toFloorId` (the cross-floor handoff).
 */
export interface WaitingInfo {
  kind: 'waiting' | 'transfer';
  /** For 'transfer': the floor id the user should move to (e.g. 'F2'). */
  toFloorId?: string;
}

/** Robot-driven escort context (screen === 'guiding' without a local session). */
export interface RobotEscortInfo {
  /** Resolved destination name to show, or null for a generic "안내중". */
  destinationName: string | null;
  /** Progress 0..1 for the bar. */
  ratio: number;
}

/**
 * Accessibility mode. `visually_impaired` is entered by the patrol wake word
 * ("hello Alfred") and adds TTS to the whole flow; it resets to `general`
 * (silent, touch-driven) once the escort finishes or the kiosk goes idle.
 */
export type KioskMode = 'general' | 'visually_impaired';

export interface KioskState {
  screen: KioskScreen;
  /** Accessibility mode (general = silent touch UI; VI = voice + TTS). */
  mode: KioskMode;
  /** Staff-call popup is an overlay, orthogonal to the screen. */
  staffCallActive: boolean;
  /** The active escort session while screen === 'guiding'. */
  session: NavigationSession | null;
  /** Active emergency detection while screen === 'alert' (requirement ver03). */
  alert: DetectionType | null;
  /** Context while screen === 'waiting' (robot-state driven). */
  waiting: WaitingInfo | null;
  /** Robot-driven escort context while screen === 'guiding' (no local session). */
  escort: RobotEscortInfo | null;
  /** Battery % while screen === 'charging' (from robot status), or null. */
  chargeBattery: number | null;
}

export type KioskEvent =
  | { type: 'WAKE' } // patrol → home (requirement #3: any key/touch)
  | { type: 'WAKE_VOICE' } // patrol → voice + VI mode (wake word "hello Alfred")
  | { type: 'OPEN_MAP' } // home → map (button A)
  | { type: 'OPEN_VOICE' } // home → voice (button B)
  | { type: 'GO_HOME' } // map/voice → home (back)
  | { type: 'START_GUIDING'; session: NavigationSession } // → guiding (#4/#5/#7)
  | { type: 'UPDATE_PROGRESS'; progress: NavigationProgress }
  | { type: 'END_GUIDING' } // guiding → patrol (requirement #10)
  | { type: 'IDLE_TIMEOUT' } // any active screen → patrol
  | { type: 'OPEN_STAFF_CALL' } // requirement #3/#11
  | { type: 'CLOSE_STAFF_CALL' }
  | { type: 'DETECTION'; detection: DetectionType } // YOLO alert (ver03) → alert
  | { type: 'CLEAR_ALERT' } // alert → patrol (staff dismiss)
  | { type: 'ENTER_CHARGING'; battery?: number } // robot DOCKING / UNDOCKING → charging
  | { type: 'ENTER_WAITING'; info: WaitingInfo } // robot WAITING / FINISHED → waiting
  | { type: 'ROBOT_ESCORT'; destinationName?: string | null; ratio?: number } // ESCORT_* → guiding
  | { type: 'EXIT_ROBOT_SCREEN' }; // robot screen → patrol (e.g. robot PATROL)
