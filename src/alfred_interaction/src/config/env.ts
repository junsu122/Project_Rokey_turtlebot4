import { DEFAULT_LANGUAGE, isLanguage, type Language } from '@/core/i18n';

/**
 * Build-time configuration from Vite env vars. Each Alfred (1F / 2F) is a
 * separate build that sets VITE_FLOOR; the backend proxy URL and language
 * default come from here too. See .env.example.
 */
function str(value: string | undefined, fallback: string): string {
  return value && value.length > 0 ? value : fallback;
}

function num(value: string | undefined, fallback: number): number {
  const n = Number(value);
  return value !== undefined && value !== '' && Number.isFinite(n)
    ? n
    : fallback;
}

const floorRaw = str(import.meta.env.VITE_FLOOR, '1')
  .toUpperCase()
  .replace('F', '');

const defaultLang = import.meta.env.VITE_DEFAULT_LANG;

export const env = {
  /** 1 or 2 — which floor this kiosk's robot serves. */
  floorNumber: floorRaw === '2' ? 2 : 1,
  /** Default UI/voice language. */
  defaultLanguage: (isLanguage(defaultLang)
    ? defaultLang
    : DEFAULT_LANGUAGE) as Language,
  /** Force mocks (no API keys / proxy needed) — for offline dev. */
  useMocks: import.meta.env.VITE_USE_MOCKS === 'true',
  /** Backend proxy base (holds Soniox + Anthropic keys). */
  apiBase: str(import.meta.env.VITE_API_BASE, '/api').replace(/\/$/, ''),
  /** Soniox real-time model. */
  sonioxModel: str(import.meta.env.VITE_SONIOX_MODEL, 'stt-rt-v4'),
  /**
   * Mic noise-gate threshold in dBFS — input quieter than this is muted before
   * STT, cutting far/background voices. Lower = more permissive (e.g. -90 ≈ off);
   * raise toward -35 to gate more aggressively. Tune per mic/room.
   */
  micGateDb: num(import.meta.env.VITE_MIC_GATE_DB, -45),
  /** Log measured mic level for tuning the gate (defaults on in dev builds). */
  micGateDebug:
    import.meta.env.VITE_MIC_GATE_DEBUG !== undefined
      ? import.meta.env.VITE_MIC_GATE_DEBUG === 'true'
      : import.meta.env.DEV,
} as const;
