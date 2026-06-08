import type { ReactNode } from 'react';
import { BigButton } from '../BigButton/BigButton';
import styles from './Modal.module.css';

interface ModalProps {
  open: boolean;
  title: string;
  description?: string;
  note?: string;
  closeLabel: string;
  onClose: () => void;
  icon?: ReactNode;
  /** Whether tapping the backdrop closes it. Off by default (#11: staff closes). */
  dismissOnBackdrop?: boolean;
  children?: ReactNode;
}

/** Centered modal dialog over a dimmed backdrop. */
export function Modal({
  open,
  title,
  description,
  note,
  closeLabel,
  onClose,
  icon,
  dismissOnBackdrop = false,
  children,
}: ModalProps) {
  if (!open) return null;

  return (
    <div
      className={styles.backdrop}
      onClick={dismissOnBackdrop ? onClose : undefined}
      role="presentation"
    >
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        {icon && (
          <div className={styles.icon} aria-hidden="true">
            {icon}
          </div>
        )}
        <h2 className={styles.title}>{title}</h2>
        {description && <p className={styles.description}>{description}</p>}
        {children}
        {note && <p className={styles.note}>{note}</p>}
        <BigButton
          label={closeLabel}
          tone="neutral"
          size="normal"
          onClick={onClose}
          className={styles.close}
        />
      </div>
    </div>
  );
}
