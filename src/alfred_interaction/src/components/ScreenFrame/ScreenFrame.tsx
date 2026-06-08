import type { ReactNode } from 'react';
import { cx } from '@/core/utils';
import styles from './ScreenFrame.module.css';

interface ScreenFrameProps {
  /** 'dark' = navy gradient (face screens), 'light' = surface (interactive). */
  tone?: 'dark' | 'light';
  children: ReactNode;
  className?: string;
}

/** Full-viewport, non-scrolling container that every screen renders inside. */
export function ScreenFrame({
  tone = 'light',
  children,
  className,
}: ScreenFrameProps) {
  return (
    <div className={cx(styles.frame, styles[tone], className)}>{children}</div>
  );
}
