import { useCallback, useEffect, useRef, useState } from 'react';
import { RobotFace, ScreenFrame } from '@/components';
import { floorLevel, kioskConfig, useStrings } from '@/config';
import { isWakeWordSupported, useAnyInput, useWakeWord } from '@/core/hooks';
import { useLanguage } from '@/core/i18n';
import { useKioskDispatch } from '@/core/kiosk';
import {
  buildInteractingRequest,
  defaultCustomer,
  useServices,
  type CustomerProfile,
} from '@/services';
import styles from './PatrolScreen.module.css';

/** Wake phrases that start the visually-impaired voice flow. */
const WAKE_WORDS = ['hello alfred', '헬로 알프레드', 'alfred', '알프레드'];

const ANNOUNCE_DELAY_MS = 2000; // first prompt shortly after entering patrol
const ANNOUNCE_INTERVAL_MS = 20000; // repeat period
const WAKE_GRACE_MS = 700; // keep wake word muted briefly after the prompt

/**
 * Requirement #2: during patrol the kiosk is a full-screen smiling face. Any
 * key/touch wakes to the (general, silent) Home (#3). Saying the wake word
 * "hello Alfred" instead jumps into the visually-impaired voice flow.
 *
 * For blind users it also announces itself periodically via TTS (so they know
 * the wake word exists). While the prompt plays — which itself contains "헬로
 * 알프레드" — wake-word recognition is muted so it doesn't trigger on its own
 * voice.
 */
export function PatrolScreen() {
  const dispatch = useKioskDispatch();
  const strings = useStrings();
  const { language } = useLanguage();
  const { tts, fms } = useServices();
  const [wakeOn, setWakeOn] = useState(true);
  /** Send the patrol→interaction INTERACTING notice at most once per visit. */
  const interactingSentRef = useRef(false);

  /**
   * Leave patrol. Publishes IF-01 INTERACTING (so the FMS marks this robot busy
   * before any destination is known), then runs the screen transition. Touch
   * → general Home (#3); wake word → visually-impaired voice flow.
   */
  const enterInteraction = useCallback(
    (profile: CustomerProfile, event: 'WAKE' | 'WAKE_VOICE') => {
      if (!interactingSentRef.current) {
        interactingSentRef.current = true;
        void fms.sendRequest(
          buildInteractingRequest({
            robotId: kioskConfig.robotId,
            origin: {
              floor: floorLevel(kioskConfig.currentFloorId),
              pose: kioskConfig.originPose,
            },
            customer: defaultCustomer(profile, language),
          }),
        );
      }
      dispatch({ type: event });
    },
    [fms, dispatch, language],
  );

  useAnyInput(() => enterInteraction('GENERAL', 'WAKE'));
  useWakeWord({
    enabled: wakeOn && isWakeWordSupported(),
    language,
    phrases: WAKE_WORDS,
    onWake: () => enterInteraction('VISUALLY_IMPAIRED', 'WAKE_VOICE'),
  });

  // Periodic self-introduction (accessibility).
  useEffect(() => {
    if (!tts.isSupported()) return;
    let cancelled = false;

    const announce = () => {
      if (cancelled) return;
      setWakeOn(false); // mute wake word while we speak our own "헬로 알프레드"
      tts.speak(strings.patrol.voicePrompt, language, {
        onEnd: () => {
          window.setTimeout(() => {
            if (!cancelled) setWakeOn(true);
          }, WAKE_GRACE_MS);
        },
      });
    };

    const first = window.setTimeout(announce, ANNOUNCE_DELAY_MS);
    const interval = window.setInterval(announce, ANNOUNCE_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(first);
      window.clearInterval(interval);
      tts.cancel();
    };
  }, [tts, language, strings]);

  return (
    <ScreenFrame tone="dark" className={styles.screen}>
      <div className={styles.body}>
        <RobotFace size="xl" />
      </div>
      <div className={styles.hints}>
        <p className={styles.hint}>{strings.patrol.hint}</p>
        <button
          type="button"
          className={styles.wake}
          onClick={(event) => {
            // Don't also trigger the window-level "any input → Home" wake.
            event.stopPropagation();
            enterInteraction('VISUALLY_IMPAIRED', 'WAKE_VOICE');
          }}
        >
          {strings.patrol.wakeHint}
        </button>
      </div>
    </ScreenFrame>
  );
}
