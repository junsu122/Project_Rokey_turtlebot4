import { useEffect, useRef } from 'react';
import { RobotFace, ScreenFrame } from '@/components';
import { useStrings } from '@/config';
import { useKioskState } from '@/core/kiosk';
import { useSpeak } from '@/services';
import styles from './ChargingScreen.module.css';

/**
 * Robot is docked / charging (IF-02 DOCKING / UNDOCKING). A calm full-screen face
 * so passers-by see the robot is just charging, not out of order. Shows the charge
 * level when the robot reports it. In VI mode the status is spoken once.
 */
export function ChargingScreen() {
  const strings = useStrings();
  const { chargeBattery } = useKioskState();
  const speak = useSpeak();
  const announcedRef = useRef(false);

  const subtitle =
    chargeBattery != null
      ? `${strings.charging.subtitle} · ${chargeBattery}%`
      : strings.charging.subtitle;

  useEffect(() => {
    if (announcedRef.current) return;
    announcedRef.current = true;
    speak(strings.charging.caption);
  }, [speak, strings]);

  return (
    <ScreenFrame tone="dark">
      <div className={styles.body}>
        <RobotFace caption={strings.charging.caption} subtitle={subtitle} />
      </div>
    </ScreenFrame>
  );
}
