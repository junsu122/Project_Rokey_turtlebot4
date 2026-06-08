import { cx } from '@/core/utils';
import styles from './StaffCallButton.module.css';

interface StaffCallButtonProps {
  label: string;
  onClick: () => void;
  className?: string;
}

/** Bottom-right "직원 호출" button (requirement #3). */
export function StaffCallButton({
  label,
  onClick,
  className,
}: StaffCallButtonProps) {
  return (
    <button
      type="button"
      className={cx(styles.button, className)}
      onClick={onClick}
    >
      <span className={styles.icon} aria-hidden="true">
        🛎️
      </span>
      <span>{label}</span>
    </button>
  );
}
