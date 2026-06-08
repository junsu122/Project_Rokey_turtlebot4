import type { Language } from '@/core/i18n';
import type { TtsService, TtsSpeakOptions } from './TtsService';

/** Logs instead of speaking — for tests / non-browser environments. */
export class MockTtsService implements TtsService {
  isSupported(): boolean {
    return true;
  }

  speak(text: string, language: Language, options?: TtsSpeakOptions): void {
    console.info(`[MockTTS:${language}] ${text}`);
    options?.onEnd?.();
  }

  cancel(): void {}
}
