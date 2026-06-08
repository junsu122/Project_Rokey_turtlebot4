import type { Language } from '@/core/i18n';

/**
 * Speech-to-text contract (requirement ver02 §2.5). Real implementation:
 * Soniox stt-rt-v4 real-time WebSocket (multilingual — §2.5.3). The UI depends
 * only on this interface.
 */
export interface SttResult {
  transcript: string;
  isFinal: boolean;
}

export interface SttHandlers {
  onResult?: (result: SttResult) => void;
  onError?: (error: Error) => void;
  /** Fires when recognition ends (after stop() or a final result). */
  onEnd?: () => void;
}

export interface SttStartOptions {
  /** Preferred language; passed to the engine as a hint (auto-detect still on). */
  language?: Language;
}

export interface SttSession {
  /** Stop listening; flushes a final result then triggers onEnd. */
  stop(): void;
}

export interface SttService {
  isSupported(): boolean;
  /** Begin a recognition session. */
  start(handlers: SttHandlers, options?: SttStartOptions): SttSession;
}
