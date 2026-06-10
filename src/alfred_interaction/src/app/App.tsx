import { kioskConfig } from '@/config';
import { LanguageProvider } from '@/core/i18n';
import { KioskProvider } from '@/core/kiosk';
import { GuidanceProvider } from '@/features/guiding';
import { AlertsProvider } from '@/features/alerts';
import { RobotStateProvider } from '@/features/robot-state';
import { ServiceProvider } from '@/services';
import { KioskApp } from './KioskApp';

/**
 * Composition root. Provider order matters:
 *   LanguageProvider (i18n) → ServiceProvider (DI) → KioskProvider (state
 *   machine) → GuidanceProvider (escort) → AlertsProvider (YOLO emergencies) →
 *   RobotStateProvider (robot status → screen) → KioskApp (shell).
 *
 * To go live, pass real implementations: <ServiceProvider services={realServices}>.
 */
export function App() {
  return (
    <LanguageProvider initialLanguage={kioskConfig.defaultLanguage}>
      <ServiceProvider>
        <KioskProvider>
          <GuidanceProvider>
            <AlertsProvider>
              <RobotStateProvider>
                <KioskApp />
              </RobotStateProvider>
            </AlertsProvider>
          </GuidanceProvider>
        </KioskProvider>
      </ServiceProvider>
    </LanguageProvider>
  );
}
