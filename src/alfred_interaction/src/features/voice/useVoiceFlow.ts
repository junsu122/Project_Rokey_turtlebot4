import { useCallback, useEffect, useRef, useState } from 'react';
import { facilities } from '@/config';
import { isSelectableFacility } from '@/core/domain';
import { useLanguage } from '@/core/i18n';
import {
  useServices,
  type SttSession,
  type VoiceUnderstanding,
} from '@/services';

/** Benches and other display-only fixtures are not voice destinations. */
const NAV_TARGETS = facilities.filter(isSelectableFacility);

/**
 * Hands-free auto-finalize for the streaming STT (Soniox emits no natural
 * "final" until we stop it). Two timers:
 *  - SILENCE_MS: stop this long after the last *new* words (end of speech).
 *    Re-armed only when the transcript actually changes, so duplicate/empty
 *    heartbeat partials don't keep it alive forever.
 *  - MAX_LISTEN_MS: an absolute cap so listening ALWAYS terminates — even with
 *    continuous background noise or if the user never speaks.
 */
const SILENCE_MS = 1500;
const MAX_LISTEN_MS = 12000;

export type VoiceState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'confirm' // facility resolved → ask to escort (§2.5.1)
  | 'chat' // general question → show conversational reply (§2.5.2)
  | 'notfound'
  | 'error';

export interface VoiceFlow {
  state: VoiceState;
  transcript: string;
  understanding: VoiceUnderstanding | null;
  startListening: () => void;
  stopListening: () => void;
}

/**
 * Drives the voice path (requirement ver02 §2.5): STT (listening) → LLM
 * understanding (thinking) → either a facility confirmation (escort + notify
 * server) or a free chat reply (no server). The selected UI language is passed
 * to both STT and the LLM.
 */
export function useVoiceFlow(): VoiceFlow {
  const { stt, llm } = useServices();
  const { language } = useLanguage();
  const [state, setState] = useState<VoiceState>('idle');
  const [transcript, setTranscript] = useState('');
  const [understanding, setUnderstanding] = useState<VoiceUnderstanding | null>(
    null,
  );
  const sessionRef = useRef<SttSession | null>(null);
  const resolvedRef = useRef(false);
  const silenceTimerRef = useRef<number | null>(null);
  const maxTimerRef = useRef<number | null>(null);
  const lastTranscriptRef = useRef('');

  const clearTimers = useCallback(() => {
    if (silenceTimerRef.current !== null) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (maxTimerRef.current !== null) {
      window.clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
  }, []);

  // Restart the end-of-speech timer (called only when new words arrive).
  const armSilence = useCallback(() => {
    if (silenceTimerRef.current !== null) {
      window.clearTimeout(silenceTimerRef.current);
    }
    silenceTimerRef.current = window.setTimeout(() => {
      sessionRef.current?.stop(); // → STT flushes a final result
    }, SILENCE_MS);
  }, []);

  const resolve = useCallback(
    async (finalText: string) => {
      if (resolvedRef.current) return;
      resolvedRef.current = true;
      clearTimers();
      if (!finalText.trim()) {
        setState('notfound');
        return;
      }
      setState('thinking');
      try {
        const result = await llm.understand(finalText, NAV_TARGETS, {
          language,
        });
        setUnderstanding(result);
        if (result.intent === 'facility') {
          setState(result.facility ? 'confirm' : 'notfound');
        } else {
          setState('chat');
        }
      } catch {
        setState('error');
      }
    },
    [llm, language, clearTimers],
  );

  const startListening = useCallback(() => {
    sessionRef.current?.stop();
    clearTimers();
    resolvedRef.current = false;
    lastTranscriptRef.current = '';
    setTranscript('');
    setUnderstanding(null);
    setState('listening');

    sessionRef.current = stt.start(
      {
        onResult: (result) => {
          if (result.isFinal) {
            clearTimers();
            setTranscript(result.transcript);
            void resolve(result.transcript);
            return;
          }
          // Only "still speaking" when the words actually changed — ignore
          // duplicate / empty heartbeat partials so the timer can elapse.
          if (result.transcript !== lastTranscriptRef.current) {
            lastTranscriptRef.current = result.transcript;
            setTranscript(result.transcript);
            if (result.transcript.trim()) armSilence();
          }
        },
        onError: () => {
          clearTimers();
          setState('error');
        },
      },
      { language },
    );

    // Absolute cap: always finalize, even under constant noise / no speech.
    maxTimerRef.current = window.setTimeout(() => {
      sessionRef.current?.stop();
    }, MAX_LISTEN_MS);
  }, [stt, resolve, language, armSilence, clearTimers]);

  const stopListening = useCallback(() => {
    clearTimers();
    sessionRef.current?.stop();
  }, [clearTimers]);

  useEffect(() => {
    return () => {
      clearTimers();
      sessionRef.current?.stop();
    };
  }, [clearTimers]);

  return { state, transcript, understanding, startListening, stopListening };
}
