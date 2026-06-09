import type { SirenKind } from '@/core/audio';
import type { Language } from '@/core/i18n';
import type { DetectionType } from '@/core/domain';

/**
 * Presentation for each emergency detection (requirement ver03). This is the
 * one file the feature owner tweaks: emoji, on-screen text, the spoken
 * announcement, which siren (or none), and the theme colour.
 */
export interface AlertSpec {
  /** Big glyph filling the screen. */
  emoji: string;
  /** Headline. */
  title: string;
  /** Instruction line under the headline. */
  detail: string;
  /** Announcement spoken (loudly) and looped while the alert shows. */
  speech: string;
  /** Siren looped under the announcement, or null (e.g. INJURED has none). */
  siren: SirenKind | null;
  /** Flashing background accent (CSS colour). */
  accent: string;
}

/** Emergency phrases are Korean — speak them with the ko voice. */
export const ALERT_SPEECH_LANG: Language = 'ko';

export const ALERTS: Record<DetectionType, AlertSpec> = {
  // 1) 화재감지 — 🔥 + 119 사이렌 + 대피 안내
  FIRE: {
    emoji: '🔥',
    title: '화재 발생',
    detail: '즉시 안전한 곳으로 대피하십시오',
    speech: '화재발생 화재발생 즉시 안전한 곳으로 대피하십시오',
    siren: 'fire',
    accent: '#ff3b30',
  },
  // 2) 부상자감지 — 🚒(소방차) + (사이렌 없음) + 119 신고 안내
  INJURED: {
    emoji: '🚒',
    title: '부상자 발생',
    detail: '119에 신고해 주세요',
    speech: '역사 내 부상자 발생 일일구에 신고해주세요',
    siren: null,
    accent: '#ff9f0a',
  },
  // 3) 거동수상자감지 — 🚨 + 112 사이렌 + 112 신고 안내
  SUSPICIOUS: {
    emoji: '🚨',
    title: '거동수상자 감지',
    detail: '112에 신고합니다',
    speech:
      '거동수상자감지 거동수상자감지 일일이에 신고하겠습니다 잡았다 요놈 잡았다 요놈',
    siren: 'police',
    accent: '#0a84ff',
  },
};
