import { DEFAULT_LANGUAGE, type Language } from '@/core/i18n';
import type {
  SttHandlers,
  SttService,
  SttSession,
  SttStartOptions,
} from './SttService';

/**
 * Simulated STT. Each session "hears" the next phrase from a rotating demo set
 * (in the requested language), streaming it word-by-word then a final result —
 * enough to drive the full voice → LLM flow with no microphone or server.
 */
const DEMO_PHRASES: Record<Language, string[]> = {
  ko: [
    '화장실 어디예요',
    '안내데스크 가고 싶어요',
    '제일 가까운 출구 알려줘',
    '엘리베이터 어디 있어요',
    '오늘 날씨 어때요',
  ],
  en: [
    'where is the restroom',
    'take me to the information desk',
    'where is the nearest exit',
    'where is the elevator',
    'what time is it',
  ],
  ja: [
    'トイレはどこですか',
    '案内デスクに行きたい',
    '一番近い出口はどこ',
    'エレベーターはどこですか',
    '今日の天気は',
  ],
  zh: ['洗手间在哪里', '我想去问询处', '最近的出口在哪', '电梯在哪里', '现在几点了'],
};

const WORD_INTERVAL_MS = 320;

export class MockSttService implements SttService {
  private index = 0;

  isSupported(): boolean {
    return true;
  }

  start(handlers: SttHandlers, options?: SttStartOptions): SttSession {
    const language = options?.language ?? DEFAULT_LANGUAGE;
    const phrases = DEMO_PHRASES[language];
    const phrase = phrases[this.index % phrases.length];
    this.index += 1;

    const words = phrase.split(' ');
    const timers: number[] = [];
    let stopped = false;

    words.forEach((_, i) => {
      timers.push(
        window.setTimeout(
          () => {
            if (stopped) return;
            handlers.onResult?.({
              transcript: words.slice(0, i + 1).join(' '),
              isFinal: false,
            });
          },
          WORD_INTERVAL_MS * (i + 1),
        ),
      );
    });

    timers.push(
      window.setTimeout(
        () => {
          if (stopped) return;
          stopped = true;
          handlers.onResult?.({ transcript: phrase, isFinal: true });
          handlers.onEnd?.();
        },
        WORD_INTERVAL_MS * (words.length + 1) + 200,
      ),
    );

    return {
      stop: () => {
        if (stopped) return;
        stopped = true;
        timers.forEach((t) => window.clearTimeout(t));
        handlers.onEnd?.();
      },
    };
  }
}
