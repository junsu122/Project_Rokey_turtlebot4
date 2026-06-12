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
  /**
   * `waiting` = robot parked, waiting for the user. `transfer` = this floor's
   * escort is done, move to `toFloorId`. `handover` = robot is driving to the
   * 2F handover/pickup point (GO_HANDOVER, just before WAITING_2F).
   */
  kind: 'waiting' | 'transfer' | 'handover';
  /** For 'transfer': the floor id the user should move to (e.g. 'F2'). */
  toFloorId?: string;
}

/** Robot-driven escort context (screen === 'guiding' without a local session). */
export interface RobotEscortInfo {
  /** Resolved destination name to show, or null for a generic "안내중". */
  destinationName: string | null;
  /** Progress 0..1 for the bar. */
  ratio: number;
  /**
   * True between the kiosk confirming a destination (IF-01 sent) and the robot
   * reporting ESCORT_1F/2F — shows a "준비 중" screen. Cleared once the robot's
   * inbound state takes over.
   */
  preparing: boolean;
  /**
   * True after the robot reports ESCORT_COMPLETED — shows the "도착했어요!" screen
   * briefly, then a timer (RobotStateProvider) returns to patrol. A trailing
   * PATROL is ignored while this holds (see EXIT_ROBOT_SCREEN).
   */
  arrived: boolean;
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
  | {
      type: 'ROBOT_ESCORT';
      destinationName?: string | null;
      ratio?: number;
      /** Kiosk-initiated, robot not yet started → show "준비 중". */
      preparing?: boolean;
    } // ESCORT_* → guiding
  | { type: 'ROBOT_ARRIVED' } // ESCORT_COMPLETED → "도착했어요!" hold → patrol
  | { type: 'EXIT_ROBOT_SCREEN' }; // robot screen → patrol (e.g. robot PATROL)
