import type { Facility } from '@/core/domain';
import type { Language } from '@/core/i18n';

/**
 * Natural-language understanding for the voice path (requirement ver02 §2.5).
 * The LLM decides whether the user wants to be guided to a facility (§2.5.1 —
 * resolve a POI, the UI then notifies the server) or is just asking a general
 * question (§2.5.2 — answer conversationally, do NOT notify the server). The
 * answer is written in the user's language (§2.5.3: ko/en/ja/zh).
 *
 * Real implementation: a server-side Claude (Haiku 4.5) call behind a proxy.
 */
export type VoiceIntent = 'facility' | 'chat';

export interface VoiceUnderstanding {
  intent: VoiceIntent;
  /** Resolved destination when intent==='facility' (null if unresolved). */
  facility: Facility | null;
  /** 0..1 confidence of the facility match. */
  confidence: number;
  /** Spoken text in the user's language: a confirmation or a chat reply. */
  reply: string;
  /** Language the reply is written in. */
  language: Language;
}

export interface LlmUnderstandOptions {
  /** UI-selected language hint (the user can still speak another language). */
  language?: Language;
}

export interface LlmService {
  understand(
    transcript: string,
    candidates: Facility[],
    options?: LlmUnderstandOptions,
  ): Promise<VoiceUnderstanding>;
}
