import { useEffect } from 'react';
import { playClick, unlockAudio } from '@/core/audio';

/**
 * Global UI sound feedback (requirement: every button plays a short click).
 * One delegated `pointerdown` listener covers ALL buttons in every screen —
 * if the press lands on (or inside) a <button>, play the click blip. The same
 * gesture also unlocks/resumes the audio context.
 */
export function useUiSounds(): void {
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      unlockAudio();
      // Real <button>s and button-like elements (e.g. SVG map fixtures).
      const target = event.target as Element | null;
      if (target?.closest('button, [role="button"]')) {
        playClick();
      }
    };
    window.addEventListener('pointerdown', onPointerDown, { passive: true });
    return () => window.removeEventListener('pointerdown', onPointerDown);
  }, []);
}
