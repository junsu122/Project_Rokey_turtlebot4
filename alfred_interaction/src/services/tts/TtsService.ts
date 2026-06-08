import type { Language } from '@/core/i18n';

/**
 * Text-to-speech contract (requirement: visually-impaired mode reads the whole
 * flow aloud). Real implementation: the browser Web Speech API (no key). Only
 * spoken in VI mode — see services/useSpeak.
 */
export interface TtsSpeakOptions {
  /** Called when speech finishes (or fails) — useful to chain speak → listen. */
  onEnd?: () => void;
}

export interface TtsService {
  isSupported(): boolean;
  /** Speak `text` in `language`. Cancels any in-progress utterance first. */
  speak(text: string, language: Language, options?: TtsSpeakOptions): void;
  cancel(): void;
}
