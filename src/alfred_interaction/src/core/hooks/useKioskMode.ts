import { useEffect } from 'react';

interface KioskModeOptions {
  /** Request browser Fullscreen on first user gesture (kiosk fallback). */
  requestFullscreen?: boolean;
  /** Hide the mouse cursor for a pure touch kiosk. */
  hideCursor?: boolean;
}

/**
 * In-app kiosk hardening (requirement #1). The browser chrome and Windows
 * taskbar are removed at LAUNCH time with Chrome's --kiosk flag (see README);
 * this hook handles what the page itself can do: block the context menu and
 * pinch gestures, and (optionally) go fullscreen / hide the cursor.
 */
export function useKioskMode({
  requestFullscreen = true,
  hideCursor = false,
}: KioskModeOptions = {}): void {
  useEffect(() => {
    const preventDefault = (event: Event) => event.preventDefault();

    document.addEventListener('contextmenu', preventDefault);
    document.addEventListener('gesturestart', preventDefault);

    const enterFullscreen = () => {
      if (!requestFullscreen) return;
      const el = document.documentElement;
      if (!document.fullscreenElement && el.requestFullscreen) {
        // User can always fall back to F11; ignore rejections.
        el.requestFullscreen().catch(() => undefined);
      }
    };

    window.addEventListener('pointerdown', enterFullscreen, { once: true });
    window.addEventListener('keydown', enterFullscreen, { once: true });

    return () => {
      document.removeEventListener('contextmenu', preventDefault);
      document.removeEventListener('gesturestart', preventDefault);
      window.removeEventListener('pointerdown', enterFullscreen);
      window.removeEventListener('keydown', enterFullscreen);
    };
  }, [requestFullscreen]);

  useEffect(() => {
    document.body.classList.toggle('kiosk-hide-cursor', hideCursor);
    return () => document.body.classList.remove('kiosk-hide-cursor');
  }, [hideCursor]);
}
