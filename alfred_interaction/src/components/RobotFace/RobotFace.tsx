import { cx } from '@/core/utils';
import styles from './RobotFace.module.css';

interface RobotFaceProps {
  /** Large line under the face (e.g. patrol hint or "시설 안내중"). */
  caption?: string;
  /** Smaller supporting line under the caption. */
  subtitle?: string;
  /** 'xl' enlarges the face (used on the patrol screen). */
  size?: 'default' | 'xl';
  className?: string;
}

/**
 * The friendly "^^" robot face shown full-screen during patrol (#2) and while
 * guiding (#7). Gentle bob + occasional blink keep it feeling alive.
 */
export function RobotFace({
  caption,
  subtitle,
  size = 'default',
  className,
}: RobotFaceProps) {
  return (
    <div className={cx(styles.wrap, className)}>
      <svg
        className={cx(styles.face, size === 'xl' && styles.faceXl)}
        viewBox="0 0 220 220"
        role="img"
        aria-label="웃는 로봇 얼굴"
      >
        <circle className={styles.head} cx="110" cy="110" r="96" />
        <g className={styles.eyes} fill="none" strokeLinecap="round">
          <path className={styles.feature} d="M58 108 Q80 78 102 108" />
          <path className={styles.feature} d="M118 108 Q140 78 162 108" />
        </g>
        <ellipse className={styles.blush} cx="64" cy="142" rx="13" ry="8" />
        <ellipse className={styles.blush} cx="156" cy="142" rx="13" ry="8" />
        <path
          className={cx(styles.feature, styles.smile)}
          d="M74 140 Q110 184 146 140"
          fill="none"
          strokeLinecap="round"
        />
      </svg>

      {caption && <p className={styles.caption}>{caption}</p>}
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
    </div>
  );
}
