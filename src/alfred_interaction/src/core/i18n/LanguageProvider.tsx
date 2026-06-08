import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { DEFAULT_LANGUAGE, type Language } from './language';

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

/**
 * Holds the active UI/voice language. The message catalog lives in config
 * (config/i18n.ts) so this stays UI-agnostic; `useStrings()` joins the two.
 */
export function LanguageProvider({
  children,
  initialLanguage = DEFAULT_LANGUAGE,
}: {
  children: ReactNode;
  initialLanguage?: Language;
}) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const value = useMemo(() => ({ language, setLanguage }), [language]);
  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error('useLanguage must be used within <LanguageProvider>');
  }
  return ctx;
}
