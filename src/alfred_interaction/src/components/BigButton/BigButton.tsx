import type { ReactNode } from 'react';
import { cx } from '@/core/utils';
import styles from './BigButton.module.css';

interface BigButtonProps {
  label: string;
  sublabel?: string;
  icon?: ReactNode;
  tone?: 'primary' | 'secondary' | 'neutral' | 'danger';
  /** 'hero' = the two giant home buttons; 'normal'/'compact' = everything else. */
  size?: 'hero' | 'normal' | 'compact';
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  ariaLabel?: string;
}

/** The single, reusable large touch button (requirement #8: everything big). */
export function BigButton({
  label,
  sublabel,
  icon,
  tone = 'primary',
  size = 'normal',
  onClick,
  disabled = false,
  className,
  ariaLabel,
}: BigButtonProps) {
  return (
    <button
      type="button"
      className={cx(styles.button, styles[tone], styles[size], className)}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel ?? label}
    >
      {icon && (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      )}
      <span className={styles.text}>
        <span className={styles.label}>{label}</span>
        {sublabel && <span className={styles.sublabel}>{sublabel}</span>}
      </span>
    </button>
  );
}
