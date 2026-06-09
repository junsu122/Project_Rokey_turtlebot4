import { useEffect, useRef } from 'react';

/**
 * Wakes the kiosk on a completed tap (`click`) or any key press.
 *
 * IMPORTANT: we listen for `click`, NOT `pointerdown`. A touch fires
 * pointerdown → pointerup → click. If we woke on pointerdown, the screen would
 * switch to Home *mid-tap*, and the SAME tap's trailing `click` would land on
 * whichever Home button ended up under the finger (it was jumping straight to
 * "음성 안내"). Waking on the terminal `click` lets the patrol screen fully
 * consume the tap, so Home opens cleanly and waits for a fresh, deliberate tap.
 */
export function useAnyInput(handler: () => void, enabled = true): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    if (!enabled) return;

    const onInput = () => handlerRef.current();
    window.addEventListener('keydown', onInput);
    window.addEventListener('click', onInput);

    return () => {
      window.removeEventListener('keydown', onInput);
      window.removeEventListener('click', onInput);
    };
  }, [enabled]);
}
