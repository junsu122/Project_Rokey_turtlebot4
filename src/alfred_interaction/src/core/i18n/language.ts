/**
 * Supported UI / voice languages (requirement ver02 §2.5.3).
 * Same codes are used as Soniox `languageHints` and the LLM reply language.
 */
export type Language = 'ko' | 'en' | 'ja' | 'zh';

export interface LanguageOption {
  code: Language;
  /** Native display name for the switcher. */
  label: string;
}

export const LANGUAGES: readonly LanguageOption[] = [
  { code: 'ko', label: '한국어' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' },
];

export const DEFAULT_LANGUAGE: Language = 'ko';

export function isLanguage(value: unknown): value is Language {
  return value === 'ko' || value === 'en' || value === 'ja' || value === 'zh';
}

/**
 * All user-facing text, one shape per language. `useStrings()` selects the
 * active catalog; see config/i18n.ts for the actual translations.
 */
export interface AppStrings {
  app: { title: string };
  lang: { label: string };
  patrol: { hint: string; wakeHint: string; voicePrompt: string };
  home: {
    greeting: (station: string) => string;
    question: string;
    buttonA: string;
    buttonADesc: string;
    buttonB: string;
    buttonBDesc: string;
    staffCall: string;
  };
  map: {
    title: string;
    subtitle: string;
    floorPickerLabel: string;
    here: string;
    back: string;
    /** Decorative train car label on the F2 blueprint. */
    train: string;
  };
  voice: {
    title: string;
    idleHint: string;
    tapToSpeak: string;
    listening: string;
    stop: string;
    thinking: string;
    youSaid: string;
    answerLabel: string;
    notFound: string;
    error: string;
    confirmQuestion: (name: string) => string;
    confirmYes: string;
    confirmRetry: string;
    askAgain: string;
    back: string;
  };
  guiding: {
    caption: string;
    toDestination: (name: string) => string;
    viaTransfer: (via: string, toFloor: string) => string;
    handoff: (toFloor: string) => string;
    arrived: string;
    cancel: string;
  };
  /** Robot docked / charging (DOCKING / UNDOCKING). */
  charging: { caption: string; subtitle: string };
  /** Robot waiting for the user / cross-floor handoff (WAITING / FINISHED). */
  waiting: {
    caption: string;
    subtitle: string;
    transfer: (toFloor: string) => string;
  };
  staff: { title: string; description: string; note: string; close: string };
}
