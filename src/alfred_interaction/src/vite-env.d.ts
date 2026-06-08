/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Which floor this Alfred serves: '1' or '2' (also accepts 'F1'/'F2'). */
  readonly VITE_FLOOR?: string;
  /** Default UI/voice language: 'ko' | 'en' | 'ja' | 'zh'. */
  readonly VITE_DEFAULT_LANG?: string;
  /** 'true' to force the mock STT/LLM services (offline dev). */
  readonly VITE_USE_MOCKS?: string;
  /** Base URL of the backend proxy (Soniox temp key + Claude). Default '/api'. */
  readonly VITE_API_BASE?: string;
  /** Soniox real-time model id. Default 'stt-rt-v4'. */
  readonly VITE_SONIOX_MODEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
