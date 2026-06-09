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

/** Emergency siren flavours (requirement ver03). */
export type SirenKind = 'fire' | 'police';

// [lowHz, highHz, halfPeriodSec] — 'fire'(119) wails slowly, 'police'(112) yelps.
const SIREN_SHAPE: Record<SirenKind, [number, number, number]> = {
  fire: [560, 1040, 0.5],
  police: [700, 1300, 0.18],
};

/**
 * Play a wailing siren for `durationMs` by sweeping one oscillator's frequency
 * back and forth (no audio assets). Returns a stop() to cut it short. The alert
 * screen loops short bursts between TTS announcements so the voice stays clear.
 */
export function playSiren(kind: SirenKind, durationMs: number): () => void {
  const c = getCtx();
  if (!c) return () => {};
  const [lo, hi, half] = SIREN_SHAPE[kind];
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = 'sawtooth';

  const now = c.currentTime;
  const end = now + durationMs / 1000;
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.linearRampToValueAtTime(0.16, now + 0.04);

  // Schedule alternating up/down frequency ramps across the whole duration.
  let t = now;
  let up = true;
  osc.frequency.setValueAtTime(lo, t);
  while (t < end) {
    const next = Math.min(t + half, end);
    osc.frequency.linearRampToValueAtTime(up ? hi : lo, next);
    t = next;
    up = !up;
  }

  gain.gain.setValueAtTime(0.16, Math.max(now + 0.04, end - 0.05));
  gain.gain.linearRampToValueAtTime(0.0001, end);
  osc.connect(gain);
  gain.connect(c.destination);
  osc.start(now);
  osc.stop(end + 0.03);

  let stopped = false;
  return () => {
    if (stopped) return;
    stopped = true;
    try {
      gain.gain.cancelScheduledValues(c.currentTime);
      gain.gain.setValueAtTime(0.0001, c.currentTime);
      osc.stop(c.currentTime + 0.02);
    } catch {
      /* already stopped */
    }
  };
}
