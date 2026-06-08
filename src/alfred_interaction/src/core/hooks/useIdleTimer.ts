import { useEffect, useRef } from 'react';

interface IdleTimerOptions {
  timeoutMs: number;
  onIdle: () => void;
  /** When false the timer is disabled (e.g. during patrol or active guiding). */
  enabled: boolean;
}

const ACTIVITY_EVENTS = [
  'pointerdown',
  'keydown',
  'touchstart',
  'mousemove',
  'wheel',
] as const;

/**
 * Fires `onIdle` after `timeoutMs` of no user activity. Used to fall back to
 * patrol if a user walks away mid-interaction (defensive support for #10).
 */
export function useIdleTimer({
  timeoutMs,
  onIdle,
  enabled,
}: IdleTimerOptions): void {
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  useEffect(() => {
    if (!enabled) return;

    let timer = 0;
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => onIdleRef.current(), timeoutMs);
    };

    ACTIVITY_EVENTS.forEach((event) =>
      window.addEventListener(event, reset, { passive: true }),
    );
    reset();

    return () => {
      window.clearTimeout(timer);
      ACTIVITY_EVENTS.forEach((event) =>
        window.removeEventListener(event, reset),
      );
    };
  }, [enabled, timeoutMs]);
}
