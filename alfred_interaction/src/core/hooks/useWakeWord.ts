import { useEffect, useRef } from 'react';
import type { Language } from '@/core/i18n';

/*
 * Wake-word detection via the browser Web Speech API (free, no key). Used during
 * patrol so the user can say "hello Alfred" / "헬로 알프레드" to enter the
 * visually-impaired voice flow. Kept separate from Soniox so the paid STT isn't
 * streaming during idle patrol. Note: Chrome's webkitSpeechRecognition uses a
 * cloud service, so it needs network + mic permission; where unsupported the
 * patrol screen falls back to a tappable hint.
 */

// Minimal Web Speech Recognition typings (not in lib.dom.d.ts).
interface SpeechAlternative {
  transcript: string;
}
interface SpeechResult {
  readonly length: number;
  isFinal: boolean;
  [index: number]: SpeechAlternative;
}
interface SpeechResultList {
  readonly length: number;
  [index: number]: SpeechResult;
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: SpeechResultList;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const LANG_TAG: Record<Language, string> = {
  ko: 'ko-KR',
  en: 'en-US',
  ja: 'ja-JP',
  zh: 'zh-CN',
};

const normalize = (value: string): string => value.replace(/\s+/g, '').toLowerCase();

export function isWakeWordSupported(): boolean {
  return getCtor() !== null;
}

interface UseWakeWordOptions {
  enabled: boolean;
  language: Language;
  /** Match terms (e.g. ["hello alfred", "헬로 알프레드"]). */
  phrases: string[];
  onWake: () => void;
}

export function useWakeWord({
  enabled,
  language,
  phrases,
  onWake,
}: UseWakeWordOptions): void {
  const onWakeRef = useRef(onWake);
  onWakeRef.current = onWake;
  const phrasesRef = useRef(phrases);
  phrasesRef.current = phrases;

  useEffect(() => {
    if (!enabled) return;
    const Ctor = getCtor();
    if (!Ctor) return;

    let stopped = false;
    let triggered = false;
    let rec: SpeechRecognitionLike | null = null;

    const matched = (text: string): boolean => {
      const t = normalize(text);
      return phrasesRef.current.some((p) => t.includes(normalize(p)));
    };

    const startRec = () => {
      if (stopped) return;
      try {
        const next = new Ctor();
        next.lang = LANG_TAG[language];
        next.continuous = true;
        next.interimResults = true;
        next.onresult = (event) => {
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            if (triggered) return;
            if (matched(event.results[i][0].transcript)) {
              triggered = true;
              stopped = true;
              try {
                next.stop();
              } catch {
                /* ignore */
              }
              onWakeRef.current();
              return;
            }
          }
        };
        next.onerror = () => {
          /* recognition restarts in onend */
        };
        next.onend = () => {
          if (!stopped) window.setTimeout(startRec, 400);
        };
        next.start();
        rec = next;
      } catch {
        // start() can throw (mic not yet permitted) — retry shortly.
        if (!stopped) window.setTimeout(startRec, 1500);
      }
    };

    startRec();

    return () => {
      stopped = true;
      try {
        rec?.abort();
      } catch {
        /* ignore */
      }
    };
  }, [enabled, language]);
}
