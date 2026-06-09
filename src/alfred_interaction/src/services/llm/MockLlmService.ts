import type { Facility } from '@/core/domain';
import { DEFAULT_LANGUAGE, type Language } from '@/core/i18n';
import type {
  LlmService,
  LlmUnderstandOptions,
  VoiceUnderstanding,
} from './LlmService';

const THINK_DELAY_MS = 700;
const MATCH_THRESHOLD = 2;

/**
 * Lightweight stand-in for a real LLM. Scores candidates by name/alias keyword
 * hits plus a floor hint; if nothing matches it falls back to a canned chat
 * reply (§2.5.2). Good enough to drive the whole voice flow offline; swap for
 * ClaudeLlmService to go live.
 */
export class MockLlmService implements LlmService {
  understand(
    transcript: string,
    candidates: Facility[],
    options?: LlmUnderstandOptions,
  ): Promise<VoiceUnderstanding> {
    const language = options?.language ?? DEFAULT_LANGUAGE;
    return new Promise((resolve) => {
      window.setTimeout(
        () => resolve(this.match(transcript, candidates, language)),
        THINK_DELAY_MS,
      );
    });
  }

  private match(
    transcript: string,
    candidates: Facility[],
    language: Language,
  ): VoiceUnderstanding {
    const text = normalize(transcript);
    const floorHint = detectFloor(text);

    let best: Facility | null = null;
    let bestScore = 0;

    for (const candidate of candidates) {
      let score = 0;
      if (text && text.includes(normalize(candidate.name))) score += 3;
      for (const alias of candidate.aliases ?? []) {
        if (text.includes(normalize(alias))) {
          score += 2;
          break;
        }
      }
      if (score > 0 && floorHint) {
        score += candidate.floorId === floorHint ? 1.5 : -0.5;
      }
      if (score > bestScore) {
        bestScore = score;
        best = candidate;
      }
    }

    if (best && bestScore >= MATCH_THRESHOLD) {
      return {
        intent: 'facility',
        facility: best,
        confidence: Math.min(1, bestScore / 4.5),
        reply: CONFIRM[language](best.name),
        language,
      };
    }

    // No facility matched → treat as a general question (§2.5.2).
    return {
      intent: 'chat',
      facility: null,
      confidence: 0,
      reply: CHAT_FALLBACK[language],
      language,
    };
  }
}

function normalize(value: string): string {
  return value.replace(/\s+/g, '').toLowerCase();
}

function detectFloor(text: string): string | null {
  if (/(2층|이층|위층|윗층|2f|2nd|2階|二楼|2楼)/.test(text)) return 'F2';
  if (/(1층|일층|아래층|아랫층|1f|1st|1階|一楼|1楼)/.test(text)) return 'F1';
  return null;
}

const CONFIRM: Record<Language, (name: string) => string> = {
  ko: (name) => `${name}(으)로 안내해 드릴게요.`,
  en: (name) => `I'll guide you to ${name}.`,
  ja: (name) => `${name}へご案内します。`,
  zh: (name) => `我来带您前往${name}。`,
};

const CHAT_FALLBACK: Record<Language, string> = {
  ko: '저는 역 안내 로봇이에요. 가까운 시설을 안내해 드릴 수 있어요. 무엇을 찾으세요?',
  en: "I'm a station guide robot. I can guide you to nearby facilities — what are you looking for?",
  ja: '私は駅の案内ロボットです。近くの施設へご案内できます。何をお探しですか？',
  zh: '我是车站向导机器人，可以带您前往附近的设施。您在找什么？',
};
