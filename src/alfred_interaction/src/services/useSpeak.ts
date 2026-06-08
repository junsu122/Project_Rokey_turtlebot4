import { useCallback } from 'react';
import { useLanguage } from '@/core/i18n';
import { useKioskState } from '@/core/kiosk';
import { useServices } from './ServiceProvider';
import type { TtsSpeakOptions } from './tts';

/**
 * Returns a speak() that talks via TTS **only in visually-impaired mode** (the
 * general mode stays silent, requirement: "일반인 모드는 TTS가 없음"). Speaks in
 * the active UI language. `onEnd` lets callers chain speak → listen.
 */
export function useSpeak(): (text: string, options?: TtsSpeakOptions) => void {
  const { tts } = useServices();
  const { language } = useLanguage();
  const { mode } = useKioskState();

  return useCallback(
    (text: string, options?: TtsSpeakOptions) => {
      if (mode !== 'visually_impaired') return;
      tts.speak(text, language, options);
    },
    [tts, language, mode],
  );
}
