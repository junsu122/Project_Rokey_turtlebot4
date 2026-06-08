import { kioskConfig } from '@/config';
import { LanguageProvider } from '@/core/i18n';
import { KioskProvider } from '@/core/kiosk';
import { GuidanceProvider } from '@/features/guiding';
import { ServiceProvider } from '@/services';
import { KioskApp } from './KioskApp';

/**
 * Composition root. Provider order matters:
 *   LanguageProvider (i18n) → ServiceProvider (DI) → KioskProvider (state
 *   machine) → GuidanceProvider (escort orchestration) → KioskApp (shell).
 *
 * To go live, pass real implementations: <ServiceProvider services={realServices}>.
 */
export function App() {
  return (
    <LanguageProvider initialLanguage={kioskConfig.defaultLanguage}>
      <ServiceProvider>
        <KioskProvider>
          <GuidanceProvider>
            <KioskApp />
          </GuidanceProvider>
        </KioskProvider>
      </ServiceProvider>
    </LanguageProvider>
  );
}
