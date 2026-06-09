import { useEffect, useRef, type CSSProperties } from 'react';
import { playSiren, unlockAudio } from '@/core/audio';
import { useKioskDispatch, useKioskState } from '@/core/kiosk';
import { useServices } from '@/services';
import { ALERTS, ALERT_SPEECH_LANG, type AlertSpec } from './alerts.config';
import styles from './AlertScreen.module.css';

const SIREN_MS = 1800; // siren burst before each announcement
const REPEAT_GAP_MS = 900; // pause after the voice before looping

/**
 * Loops the emergency audio while the alert shows: siren burst → spoken
 * announcement → gap → repeat (sequenced, not overlapped, so the voice stays
 * intelligible). INJURED has no siren, so it just repeats the announcement.
 * Everything stops on unmount (alert cleared).
 */
function useEmergencyAudio(spec: AlertSpec | null): void {
  const { tts } = useServices();
  const stopSirenRef = useRef<(() => void) | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!spec) return;
    let cancelled = false;
    unlockAudio();

    const announce = () => {
      if (cancelled) return;
      tts.speak(spec.speech, ALERT_SPEECH_LANG, {
        volume: 1, // max — emergency announcement
        rate: 1.02,
        onEnd: () => {
          if (cancelled) return;
          timerRef.current = window.setTimeout(runCycle, REPEAT_GAP_MS);
        },
      });
    };

    const runCycle = () => {
      if (cancelled) return;
      if (spec.siren) {
        stopSirenRef.current = playSiren(spec.siren, SIREN_MS);
        timerRef.current = window.setTimeout(announce, SIREN_MS + 120);
      } else {
        announce();
      }
    };

    runCycle();

    return () => {
      cancelled = true;
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      timerRef.current = null;
      stopSirenRef.current?.();
      stopSirenRef.current = null;
      tts.cancel();
    };
  }, [spec, tts]);
}

/**
 * Full-screen emergency alert (requirement ver03). A YOLO detection takes over
 * the whole kiosk: flashing themed background, giant emoji + headline, a looping
 * siren/voice announcement, and a staff "경보 해제" button to dismiss back to
 * patrol. Rendered by KioskRouter when screen === 'alert'.
 */
export function AlertScreen() {
  const { alert } = useKioskState();
  const dispatch = useKioskDispatch();
  const spec = alert ? ALERTS[alert] : null;

  useEmergencyAudio(spec);

  if (!spec) return null;

  return (
    <div
      className={styles.root}
      style={{ '--alert-accent': spec.accent } as CSSProperties}
    >
      <div className={styles.flash} aria-hidden />
      <div className={styles.body} role="alert">
        <div className={styles.emoji}>{spec.emoji}</div>
        <h1 className={styles.title}>{spec.title}</h1>
        <p className={styles.detail}>{spec.detail}</p>
      </div>
      <button
        type="button"
        className={styles.dismiss}
        onClick={() => dispatch({ type: 'CLEAR_ALERT' })}
      >
        경보 해제
      </button>
    </div>
  );
}
