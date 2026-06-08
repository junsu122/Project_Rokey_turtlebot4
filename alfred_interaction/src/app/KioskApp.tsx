import { kioskConfig } from '@/config';
import { useIdleTimer, useKioskMode, useUiSounds } from '@/core/hooks';
import { useKioskDispatch, useKioskState } from '@/core/kiosk';
import { KioskRouter } from './KioskRouter';
import { StaffCallOverlay } from './StaffCallOverlay';
import styles from './App.module.css';

/**
 * Kiosk shell: applies kiosk-mode hardening, runs the idle→patrol timer on
 * interactive screens, and renders the current screen plus the staff overlay.
 */
export function KioskApp() {
  const { screen } = useKioskState();
  const dispatch = useKioskDispatch();

  useKioskMode({
    requestFullscreen: kioskConfig.requestFullscreen,
    hideCursor: kioskConfig.hideCursor,
  });

  // Short click sound on every button press (all screens).
  useUiSounds();

  const idleEnabled =
    screen === 'home' || screen === 'map' || screen === 'voice';

  useIdleTimer({
    timeoutMs: kioskConfig.idleTimeoutMs,
    enabled: idleEnabled,
    onIdle: () => dispatch({ type: 'IDLE_TIMEOUT' }),
  });

  return (
    <div className={styles.app}>
      <KioskRouter />
      <StaffCallOverlay />
    </div>
  );
}
