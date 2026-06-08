import { useEffect, useRef } from 'react';
import { RobotFace, ScreenFrame } from '@/components';
import { getFloor, useStrings } from '@/config';
import { playBeep } from '@/core/audio';
import { useLanguage, type AppStrings, type Language } from '@/core/i18n';
import { localizedFacilityName, type NavigationSession } from '@/core/domain';
import { useKioskState } from '@/core/kiosk';
import { useSpeak } from '@/services';
import { useGuidance } from './GuidanceProvider';
import styles from './GuidingScreen.module.css';

/**
 * Requirement #7 / ver02 §2.2: while escorting, the kiosk shows the smiling face
 * with the "시설 안내중" caption. The subtitle reflects same-floor vs the
 * cross-floor handoff (#6). On arrival it briefly celebrates, then returns to
 * patrol (#10). In visually-impaired mode the trip and arrival are spoken (TTS).
 */
export function GuidingScreen() {
  const { session, mode } = useKioskState();
  const strings = useStrings();
  const { language } = useLanguage();
  const { cancelGuidance } = useGuidance();
  const speak = useSpeak();
  const announcedRef = useRef(false);
  const arrivedAnnouncedRef = useRef(false);

  const arrived = session?.progress.phase === 'arrived';
  const vi = mode === 'visually_impaired';
  const hasSession = !!session;

  // VI mode: announce the trip once on entry, and the arrival when reached.
  useEffect(() => {
    if (!session || announcedRef.current) return;
    announcedRef.current = true;
    speak(describe(session, strings, language));
  }, [session, speak, strings, language]);

  useEffect(() => {
    if (arrived && !arrivedAnnouncedRef.current) {
      arrivedAnnouncedRef.current = true;
      speak(strings.guiding.arrived);
    }
  }, [arrived, speak, strings]);

  // VI mode: repeating locator beep so the user can find / follow this Alfred
  // while it escorts (stops on arrival). Booleans-only deps so progress ticks
  // don't restart the interval.
  useEffect(() => {
    if (!vi || !hasSession || arrived) return;
    playBeep();
    const id = window.setInterval(playBeep, 1000);
    return () => window.clearInterval(id);
  }, [vi, hasSession, arrived]);

  if (!session) return null;

  const caption = arrived ? strings.guiding.arrived : strings.guiding.caption;
  const subtitle = arrived ? undefined : describe(session, strings, language);
  const ratio = Math.min(1, Math.max(0, session.progress.ratio));

  return (
    <ScreenFrame tone="dark">
      <div className={styles.body}>
        <RobotFace caption={caption} subtitle={subtitle} />
        <div className={styles.progress} aria-hidden="true">
          <div
            className={styles.progressFill}
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
      </div>

      {!arrived && (
        <button type="button" className={styles.cancel} onClick={cancelGuidance}>
          {strings.guiding.cancel}
        </button>
      )}
    </ScreenFrame>
  );
}

function describe(
  session: NavigationSession,
  strings: AppStrings,
  language: Language,
): string {
  const { plan, progress } = session;

  if (plan.kind === 'cross-floor' && plan.transfer) {
    const toFloor = getFloor(plan.transfer.toFloorId)?.shortName ?? '';
    if (progress.phase === 'awaiting-handoff') {
      return strings.guiding.handoff(toFloor);
    }
    return strings.guiding.viaTransfer(
      localizedFacilityName(plan.transfer.via, language),
      toFloor,
    );
  }

  return strings.guiding.toDestination(
    localizedFacilityName(plan.destination, language),
  );
}
