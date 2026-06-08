/**
 * Tiny sound-effects helper built on the Web Audio API (no assets, offline, no
 * key). Used for the button "click" feedback and the visually-impaired locator
 * beep. A single shared AudioContext is created lazily and resumed on demand
 * (the kiosk launches Chrome with --autoplay-policy=no-user-gesture-required,
 * so it can start without a tap; `unlockAudio()` also resumes it on first input).
 */
let ctx: AudioContext | null = null;

function getCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    AudioContext?: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  };
  const Ctor = w.AudioContext ?? w.webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  if (ctx.state === 'suspended') void ctx.resume();
  return ctx;
}

/** Resume the audio context (call on a user gesture / first input). */
export function unlockAudio(): void {
  getCtx();
}

function tone(freq: number, durationMs: number, gainValue: number): void {
  const c = getCtx();
  if (!c) return;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq;
  const now = c.currentTime;
  const dur = durationMs / 1000;
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.linearRampToValueAtTime(gainValue, now + 0.006);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);
  osc.connect(gain);
  gain.connect(c.destination);
  osc.start(now);
  osc.stop(now + dur + 0.02);
}

/** Short, crisp "button pressed" blip. */
export function playClick(): void {
  tone(1150, 45, 0.16);
}

/** Locator beep for VI navigation (so the user can find this Alfred). */
export function playBeep(): void {
  tone(880, 170, 0.1);
}
