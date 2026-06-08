import { SonioxClient } from '@soniox/speech-to-text-web';
import { LANGUAGES, type Language } from '@/core/i18n';
import type {
  SttHandlers,
  SttService,
  SttSession,
  SttStartOptions,
} from './SttService';

export interface SonioxSttConfig {
  /** Proxy endpoint that mints a Soniox temporary API key, e.g.
   * `${apiBase}/soniox/temporary-api-key`. The permanent key stays server-side. */
  temporaryKeyEndpoint: string;
  /** Real-time model id (default 'stt-rt-v4'). */
  model: string;
  /**
   * Noise-gate threshold in dBFS. Mic input quieter than this is muted *before*
   * it reaches Soniox, so distant/background speech (which arrives quieter) isn't
   * transcribed — a loudness proxy for "near-field only". Lower = more permissive
   * (e.g. -90 ≈ effectively off). Tune per mic/room.
   */
  gateDb: number;
  /** Log the measured mic level so the gate threshold can be tuned. */
  gateDebug?: boolean;
}

/** Minimal shape of a Soniox partial result (structurally compatible). */
interface SonioxPartialResult {
  tokens: Array<{ text: string; is_final?: boolean }>;
}

const ALL_HINTS: Language[] = LANGUAGES.map((l) => l.code);

/** How long the gate stays open after the last above-threshold frame (ms). */
const GATE_HOLD_MS = 300;

/**
 * Real-time STT via Soniox stt-rt-v4 (requirement ver02 §2.5 / §2.5.3).
 *
 * The browser never holds the permanent Soniox key: SonioxClient fetches a
 * short-lived temporary key from our proxy. We capture the mic ourselves, run it
 * through a loudness gate (see createNoiseGate), and stream the GATED audio to
 * Soniox — so distant/background voices below the threshold are never sent.
 * Final tokens are appended; non-final tokens form the live tail. stop() flushes
 * a final transcript and releases the mic.
 */
export class SonioxSttService implements SttService {
  constructor(private readonly config: SonioxSttConfig) {}

  isSupported(): boolean {
    return (
      typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
    );
  }

  start(handlers: SttHandlers, options?: SttStartOptions): SttSession {
    const endpoint = this.config.temporaryKeyEndpoint;

    const client = new SonioxClient({
      apiKey: async () => {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ usage_type: 'transcribe_websocket' }),
        });
        if (!res.ok) {
          throw new Error(`Soniox temporary key error: ${res.status}`);
        }
        const data = (await res.json()) as {
          api_key?: string;
          apiKey?: string;
        };
        const key = data.api_key ?? data.apiKey;
        if (!key) throw new Error('Soniox temporary key missing in response');
        return key;
      },
    });

    let finalText = '';
    let lastTranscript = '';
    let ended = false;

    const end = () => {
      if (ended) return;
      ended = true;
      handlers.onEnd?.();
    };

    // Prefer the selected language but keep the others as hints + auto-detect.
    const hints = options?.language
      ? [options.language, ...ALL_HINTS.filter((c) => c !== options.language)]
      : ALL_HINTS;

    let gate: NoiseGate | null = null;
    let cancelled = false;

    // Acquire the mic ourselves → gate by loudness → feed the gated stream to
    // Soniox (its `stream` option), so far/quiet speech never reaches the engine.
    void (async () => {
      let raw: MediaStream;
      try {
        raw = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: false, // don't amplify far/quiet sound
          },
        });
      } catch (err) {
        // Mic blocked / no device.
        handlers.onError?.(
          err instanceof Error ? err : new Error('microphone error'),
        );
        end();
        return;
      }

      if (cancelled) {
        raw.getTracks().forEach((t) => t.stop());
        return;
      }

      const g = createNoiseGate(raw, {
        thresholdDb: this.config.gateDb,
        debug: this.config.gateDebug,
      });
      gate = g;

      if (cancelled) {
        g.close();
        return;
      }

      client.start({
        model: this.config.model,
        languageHints: hints,
        enableLanguageIdentification: true,
        stream: g.stream, // gated mic stream
        onPartialResult: (result: SonioxPartialResult) => {
          let interim = '';
          for (const token of result.tokens) {
            if (token.is_final) finalText += token.text;
            else interim += token.text;
          }
          lastTranscript = finalText + interim;
          handlers.onResult?.({ transcript: lastTranscript, isFinal: false });
        },
        onFinished: () => {
          handlers.onResult?.({
            transcript: finalText || lastTranscript,
            isFinal: true,
          });
          end();
        },
        onError: (status: string, message: string) => {
          handlers.onError?.(new Error(`Soniox ${status}: ${message}`));
          end();
        },
      });
    })();

    return {
      stop: () => {
        cancelled = true;
        // Graceful: waits for buffered audio, then onFinished fires.
        try {
          client.stop();
        } catch {
          /* not started yet */
        }
        gate?.close();
      },
    };
  }
}

interface NoiseGate {
  /** Gated output stream to feed downstream. */
  stream: MediaStream;
  /** Tear down the audio graph and release the mic. */
  close: () => void;
}

/**
 * A loudness gate on the Web Audio API: every frame it measures the input RMS
 * level and mutes the output (gain → 0) while it stays below `thresholdDb`.
 * Quiet/distant speech is dropped; near speech (louder) passes. Fast attack + a
 * short release/hold keep word tails from being clipped.
 */
function createNoiseGate(
  input: MediaStream,
  opts: { thresholdDb: number; debug?: boolean },
): NoiseGate {
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  const ctx = new Ctor();
  void ctx.resume();

  const source = ctx.createMediaStreamSource(input);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  const gain = ctx.createGain();
  gain.gain.value = 0; // start closed
  const dest = ctx.createMediaStreamDestination();

  source.connect(analyser); // measurement tap (not routed to output)
  source.connect(gain);
  gain.connect(dest); // gated output

  const buf = new Float32Array(analyser.fftSize);
  let holdUntil = 0;
  let raf = 0;
  let lastLog = 0;

  const tick = () => {
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i += 1) sum += buf[i] * buf[i];
    const db = 20 * Math.log10(Math.sqrt(sum / buf.length) + 1e-9);
    const now = performance.now();
    if (db >= opts.thresholdDb) holdUntil = now + GATE_HOLD_MS;
    const open = now < holdUntil;
    // Fast attack (open), slower release (close) to preserve word tails.
    gain.gain.setTargetAtTime(open ? 1 : 0, ctx.currentTime, open ? 0.01 : 0.06);

    if (opts.debug && now - lastLog > 400) {
      lastLog = now;
      console.info(
        `[mic-gate] ${db.toFixed(1)} dB (thr ${opts.thresholdDb}) → ${open ? 'OPEN' : 'muted'}`,
      );
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  return {
    stream: dest.stream,
    close: () => {
      cancelAnimationFrame(raf);
      try {
        source.disconnect();
        analyser.disconnect();
        gain.disconnect();
      } catch {
        /* ignore */
      }
      input.getTracks().forEach((t) => t.stop());
      void ctx.close();
    },
  };
}
