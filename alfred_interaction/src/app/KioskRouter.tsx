import { useKioskState } from '@/core/kiosk';
import { PatrolScreen } from '@/features/patrol/PatrolScreen';
import { HomeScreen } from '@/features/home/HomeScreen';
import { MapScreen } from '@/features/map/MapScreen';
import { VoiceScreen } from '@/features/voice/VoiceScreen';
import { GuidingScreen } from '@/features/guiding';

/** Maps the kiosk's current state to its screen — the only place screens mount. */
export function KioskRouter() {
  const { screen } = useKioskState();

  switch (screen) {
    case 'home':
      return <HomeScreen />;
    case 'map':
      return <MapScreen />;
    case 'voice':
      return <VoiceScreen />;
    case 'guiding':
      return <GuidingScreen />;
    case 'patrol':
    default:
      return <PatrolScreen />;
  }
}
