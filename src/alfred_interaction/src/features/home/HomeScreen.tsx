import {
  BigButton,
  LanguageSwitcher,
  ScreenFrame,
  StaffCallButton,
} from '@/components';
import { getFloorOrThrow, kioskConfig, useStrings } from '@/config';
import { useKioskDispatch } from '@/core/kiosk';
import styles from './HomeScreen.module.css';

/**
 * Requirement #3 / ver02 §2.1, §2.3: the initial UI — two large buttons
 * (A=map, B=voice) centered, a floor badge + language switcher on top, and a
 * "직원 호출" button at the bottom-right.
 */
export function HomeScreen() {
  const dispatch = useKioskDispatch();
  const strings = useStrings();
  const floor = getFloorOrThrow(kioskConfig.currentFloorId);

  return (
    <ScreenFrame tone="light">
      <div className={styles.topbar}>
        <span className={styles.floorBadge}>{floor.shortName}</span>
        <LanguageSwitcher />
      </div>

      <header className={styles.header}>
        <p className={styles.greeting}>
          {strings.home.greeting(kioskConfig.stationName)}
        </p>
        <h1 className={styles.question}>{strings.home.question}</h1>
      </header>

      <div className={styles.buttons}>
        <BigButton
          tone="primary"
          size="hero"
          icon="🗺️"
          label={strings.home.buttonA}
          sublabel={strings.home.buttonADesc}
          onClick={() => dispatch({ type: 'OPEN_MAP' })}
          className={styles.hero}
        />
        <BigButton
          tone="secondary"
          size="hero"
          icon="🎤"
          label={strings.home.buttonB}
          sublabel={strings.home.buttonBDesc}
          onClick={() => dispatch({ type: 'OPEN_VOICE' })}
          className={styles.hero}
        />
      </div>

      <StaffCallButton
        label={strings.home.staffCall}
        onClick={() => dispatch({ type: 'OPEN_STAFF_CALL' })}
      />
    </ScreenFrame>
  );
}
