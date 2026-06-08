import type { NavigationProgress, NavigationSession } from '@/core/domain';

/** The five top-level kiosk screens (the finite states). */
export type KioskScreen = 'patrol' | 'home' | 'map' | 'voice' | 'guiding';

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
  | { type: 'CLOSE_STAFF_CALL' };
