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
interface SpeechRecognitionErrorEventLike {
  error: string;
  message?: string;
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
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
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
            const transcript = event.results[i][0].transcript;
            // DIAGNOSTIC: what the cloud STT actually heard (catches the
            // "heard '알프레도' but didn't match '알프레드'" case).
            console.debug('[wakeword] heard:', JSON.stringify(transcript), 'final?', event.results[i].isFinal);
            if (matched(transcript)) {
              triggered = true;
              stopped = true;
              try {
                next.stop();
              } catch {
                /* ignore */
              }
              console.info('[wakeword] MATCH →', JSON.stringify(transcript));
              onWakeRef.current();
              return;
            }
          }
        };
        next.onerror = (event) => {
          // DIAGNOSTIC: the reason it's silent. Common codes:
          //   network            → no internet (Web Speech is a Google cloud service)
          //   not-allowed        → mic blocked (insecure http://IP context or denied)
          //   service-not-allowed→ STT service blocked / unsupported origin
          //   audio-capture      → no mic / mic held by another app (e.g. Soniox)
          //   no-speech/aborted  → silence or restart churn (often benign)
          console.warn('[wakeword] error:', event.error, event.message ?? '');
        };
        next.onend = () => {
          console.debug('[wakeword] onend (restart in 400ms)', { stopped });
          if (!stopped) window.setTimeout(startRec, 400);
        };
        next.start();
        console.debug('[wakeword] start; lang =', next.lang, 'phrases =', phrasesRef.current);
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
