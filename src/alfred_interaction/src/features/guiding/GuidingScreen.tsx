import { useEffect, useRef } from 'react';
import { RobotFace, ScreenFrame } from '@/components';
import { getFloor, useStrings } from '@/config';
import { playBeep } from '@/core/audio';
import { useLanguage, type AppStrings, type Language } from '@/core/i18n';
import { localizedFacilityName, type NavigationSession } from '@/core/domain';
import { useKioskState } from '@/core/kiosk';
import { cx } from '@/core/utils';
import { useSpeak } from '@/services';
import { useGuidance } from './GuidanceProvider';
import styles from './GuidingScreen.module.css';

/**
 * Requirement #7 / ver02 §2.2: while escorting, the kiosk shows the smiling face
 * with the "시설 안내중" caption. Driven by EITHER the local escort (user picked a
 * destination on the kiosk → rich `session` with cross-floor handoff #6) OR an
 * inbound robot escort (IF-02 ESCORT_1F/2F → `escort` with destination + progress).
 * In visually-impaired mode the trip and arrival are spoken (TTS).
 */
export function GuidingScreen() {
  const { session, escort, mode } = useKioskState();
  const strings = useStrings();
  const { language } = useLanguage();
  const { cancelGuidance } = useGuidance();
  const speak = useSpeak();
  const announcedRef = useRef(false);
  const arrivedAnnouncedRef = useRef(false);

  const arrived = session?.progress.phase === 'arrived' || !!escort?.arrived;
  const vi = mode === 'visually_impaired';
  const hasContent = !!session || !!escort;
  // Kiosk confirmed a destination but the robot hasn't reported ESCORT_* yet.
  const preparing = !session && !!escort?.preparing;
  // Only a local (user-initiated) escort can be cancelled from the kiosk; the
  // robot owns its own escort.
  const canCancel = !!session && !arrived;

  const caption = preparing
    ? strings.guiding.preparing
    : arrived
      ? strings.guiding.arrived
      : strings.guiding.caption;
  // Subtitle: nothing on arrival; else rich from the local session, else the
  // robot-provided destination.
  const subtitle = arrived
    ? undefined
    : session
      ? describe(session, strings, language)
      : escort?.destinationName
        ? preparing
          ? strings.guiding.preparingTo(escort.destinationName)
          : strings.guiding.toDestination(escort.destinationName)
        : undefined;
  const ratio = Math.min(
    1,
    Math.max(0, session ? session.progress.ratio : escort?.ratio ?? 0),
  );
  // Robot-driven escort reports no progress %, so show an indeterminate (animated)
  // bar instead of a permanently-empty one. The bar is hidden once arrived.
  const robotDriven = !!escort && !session;
  const indeterminate = !arrived && robotDriven && ratio <= 0;
  const showProgress = hasContent && !arrived;

  // VI mode: announce the trip once on entry (session subtitle or robot name).
  useEffect(() => {
    if (!hasContent || announcedRef.current) return;
    announcedRef.current = true;
    speak(subtitle ?? caption);
  }, [hasContent, subtitle, caption, speak]);

  useEffect(() => {
    if (arrived && !arrivedAnnouncedRef.current) {
      arrivedAnnouncedRef.current = true;
      speak(strings.guiding.arrived);
    }
  }, [arrived, speak, strings]);

  // VI mode: repeating locator beep while escorting (stops on arrival). Booleans-
  // only deps so progress ticks don't restart the interval.
  useEffect(() => {
    if (!vi || !hasContent || arrived) return;
    playBeep();
    const id = window.setInterval(playBeep, 1000);
    return () => window.clearInterval(id);
  }, [vi, hasContent, arrived]);

  if (!hasContent) return null;

  return (
    <ScreenFrame tone="dark">
      <div className={styles.body}>
        <RobotFace caption={caption} subtitle={subtitle} />
        {showProgress && (
          <div
            className={cx(styles.progress, indeterminate && styles.indeterminate)}
            aria-hidden="true"
          >
            {!indeterminate && (
              <div
                className={styles.progressFill}
                style={{ width: `${Math.round(ratio * 100)}%` }}
              />
            )}
          </div>
        )}
      </div>

      {canCancel && (
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
