import type { Facility } from '@/core/domain';
import { DEFAULT_LANGUAGE, isLanguage } from '@/core/i18n';
import type {
  LlmService,
  LlmUnderstandOptions,
  VoiceUnderstanding,
} from './LlmService';

export interface ClaudeLlmConfig {
  /** Proxy endpoint, e.g. `${apiBase}/llm/understand`. The proxy calls Claude
   * Haiku 4.5 server-side (key stays off the kiosk). */
  endpoint: string;
}

interface ProxyResponse {
  intent: 'facility' | 'chat';
  poi_id: string | null;
  confidence: number;
  reply: string;
  language: string;
}

/**
 * Real LLM via the backend proxy. The browser never holds the Anthropic key:
 * it POSTs the transcript + candidate POIs to the proxy, which runs Claude
 * Haiku 4.5 with structured outputs and returns the intent/POI/reply.
 */
export class ClaudeLlmService implements LlmService {
  constructor(private readonly config: ClaudeLlmConfig) {}

  async understand(
    transcript: string,
    candidates: Facility[],
    options?: LlmUnderstandOptions,
  ): Promise<VoiceUnderstanding> {
    const res = await fetch(this.config.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript,
        language: options?.language,
        candidates: candidates.map((c) => ({
          poi_id: c.poiId,
          name: c.name,
          floor: c.floorId,
          aliases: c.aliases ?? [],
        })),
      }),
    });

    if (!res.ok) {
      throw new Error(`LLM proxy error: ${res.status}`);
    }

    const data = (await res.json()) as ProxyResponse;
    const language = isLanguage(data.language)
      ? data.language
      : (options?.language ?? DEFAULT_LANGUAGE);
    const facility = data.poi_id
      ? (candidates.find((c) => c.poiId === data.poi_id) ?? null)
      : null;
    const intent = data.intent === 'facility' ? 'facility' : 'chat';

    return {
      intent,
      facility,
      confidence:
        typeof data.confidence === 'number'
          ? data.confidence
          : facility
            ? 0.8
            : 0,
      reply: data.reply ?? '',
      language,
    };
  }
}
