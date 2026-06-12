import { useEffect, useRef } from 'react';
import { RobotFace, ScreenFrame } from '@/components';
import { getFloor, useStrings } from '@/config';
import { useKioskState } from '@/core/kiosk';
import { useSpeak } from '@/services';
import styles from './WaitingScreen.module.css';

/**
 * Robot is waiting for the user, or this floor's escort is done and the user
 * should move floors (IF-02 WAITING_* / ESCORT_*_FINISHED, cross-floor handoff #6).
 * A 'transfer' tells the user which floor to head to. Spoken once in VI mode.
 */
export function WaitingScreen() {
  const { waiting } = useKioskState();
  const strings = useStrings();
  const speak = useSpeak();
  const announcedRef = useRef(false);

  const toFloor = waiting?.toFloorId
    ? getFloor(waiting.toFloorId)?.shortName ?? ''
    : '';
  const handover = waiting?.kind === 'handover';
  const caption =
    waiting?.kind === 'transfer'
      ? strings.waiting.transfer(toFloor)
      : handover
        ? strings.waiting.handover
        : strings.waiting.caption;
  const subtitle = handover
    ? strings.waiting.handoverSub
    : strings.waiting.subtitle;

  useEffect(() => {
    if (announcedRef.current) return;
    announcedRef.current = true;
    speak(caption);
  }, [speak, caption]);

  return (
    <ScreenFrame tone="dark">
      <div className={styles.body}>
        <RobotFace caption={caption} subtitle={subtitle} />
      </div>
    </ScreenFrame>
  );
}
