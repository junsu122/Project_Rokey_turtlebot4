import type { Language } from '@/core/i18n';
import type { TtsService, TtsSpeakOptions } from './TtsService';

const LANG_TAG: Record<Language, string> = {
  ko: 'ko-KR',
  en: 'en-US',
  ja: 'ja-JP',
  zh: 'zh-CN',
};

/**
 * Browser-native TTS (speechSynthesis). Free, offline, no key — works in both
 * mock and live builds. Degrades to a no-op (firing onEnd) where unsupported.
 */
export class WebSpeechTtsService implements TtsService {
  isSupported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  speak(text: string, language: Language, options?: TtsSpeakOptions): void {
    if (!this.isSupported() || !text) {
      options?.onEnd?.();
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel(); // never overlap utterances
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = LANG_TAG[language];
    if (options?.onEnd) {
      utter.onend = () => options.onEnd?.();
      utter.onerror = () => options.onEnd?.(); // don't hang chained actions
    }
    synth.speak(utter);
  }

  cancel(): void {
    if (this.isSupported()) window.speechSynthesis.cancel();
  }
}
