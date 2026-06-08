// ============================================================================
//  ALFRED backend proxy — keeps the Soniox + Anthropic keys off the kiosk.
//
//  The browser UI talks ONLY to this proxy (see VITE_API_BASE / Vite dev proxy):
//   • POST /api/soniox/temporary-api-key  → mints a short-lived Soniox key so the
//        browser can open the stt-rt-v4 WebSocket without the permanent key.
//   • POST /api/llm/understand            → runs Claude Haiku 4.5 (official
//        Anthropic SDK + structured outputs) to classify facility-vs-chat and
//        pick a POI (requirement ver02 §2.5).
//
//  Run:  ANTHROPIC_API_KEY=... SONIOX_API_KEY=... node server/proxy.mjs
//  (or put them in user_interface/.env — see .env.example)
// ============================================================================
import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import Anthropic from '@anthropic-ai/sdk';
import { z } from 'zod';
import { zodOutputFormat } from '@anthropic-ai/sdk/helpers/zod';

const PORT = Number(process.env.PORT ?? 8787);
const SONIOX_API_KEY = process.env.SONIOX_API_KEY;
const SONIOX_TEMP_KEY_TTL = Number(process.env.SONIOX_TEMP_KEY_TTL ?? 300);
const LLM_MODEL = process.env.LLM_MODEL ?? 'claude-haiku-4-5';

const anthropic = new Anthropic(); // reads ANTHROPIC_API_KEY from the env

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));

// ---- Structured output schema for the voice understanding (§2.5) ----
const Understanding = z.object({
  intent: z.enum(['facility', 'chat']),
  poi_id: z.string().nullable(),
  confidence: z.number(),
  reply: z.string(),
  language: z.enum(['ko', 'en', 'ja', 'zh']),
});

const SYSTEM_PROMPT = `You are ALFRED, a friendly subway-station guide robot on a touch kiosk.
A user spoke to you. Decide what they want:

- intent "facility": they want to be guided to a station facility (restroom, exit,
  info desk, elevator, gate, platform, transfer, etc.). Choose the single best
  matching POI from the provided candidate list and put its poi_id. If they clearly
  want guidance but none of the candidates match, set poi_id to null.
- intent "chat": anything else (small talk, the weather, the time, general
  questions). poi_id must be null. Answer the question briefly and warmly.

Rules:
- Detect the language the user actually spoke and set "language" to one of
  ko, en, ja, zh. Write "reply" in THAT language.
- For intent "facility", "reply" is a short confirmation, e.g. "I'll guide you to the restroom."
- For intent "chat", "reply" is a short, helpful answer (1-2 sentences).
- "confidence" is 0..1 for how sure you are about the facility match (0 for chat).
- Only ever use poi_id values that appear in the candidate list.`;

app.post('/api/llm/understand', async (req, res) => {
  try {
    const { transcript, language, candidates } = req.body ?? {};
    if (typeof transcript !== 'string' || !transcript.trim()) {
      return res.status(400).json({ error: 'transcript required' });
    }

    const userContent = [
      language ? `UI language hint: ${language}` : '',
      'Candidate facilities (poi_id — name — floor — aliases):',
      ...(Array.isArray(candidates) ? candidates : []).map(
        (c) =>
          `- ${c.poi_id} — ${c.name} — ${c.floor} — ${(c.aliases ?? []).join(', ')}`,
      ),
      '',
      `User said: "${transcript}"`,
    ]
      .filter(Boolean)
      .join('\n');

    const message = await anthropic.messages.parse({
      model: LLM_MODEL,
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: userContent }],
      output_config: { format: zodOutputFormat(Understanding) },
    });

    const out = message.parsed_output;
    if (!out) {
      return res
        .status(502)
        .json({ error: 'model returned no structured output' });
    }
    return res.json(out);
  } catch (err) {
    console.error('[llm] error', err);
    return res.status(500).json({ error: 'llm_failed' });
  }
});

app.post('/api/soniox/temporary-api-key', async (_req, res) => {
  try {
    if (!SONIOX_API_KEY) {
      return res.status(500).json({ error: 'SONIOX_API_KEY not configured' });
    }
    const upstream = await fetch(
      'https://api.soniox.com/v1/auth/temporary-api-key',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${SONIOX_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          usage_type: 'transcribe_websocket',
          expires_in_seconds: SONIOX_TEMP_KEY_TTL,
        }),
      },
    );
    if (!upstream.ok) {
      const text = await upstream.text();
      console.error('[soniox] temp key error', upstream.status, text);
      return res.status(502).json({ error: 'soniox_temp_key_failed' });
    }
    const data = await upstream.json();
    // Soniox returns { api_key, expires_at, ... }; forward just the key.
    return res.json({ api_key: data.api_key, expires_at: data.expires_at });
  } catch (err) {
    console.error('[soniox] error', err);
    return res.status(500).json({ error: 'soniox_failed' });
  }
});

app.get('/api/health', (_req, res) =>
  res.json({
    ok: true,
    soniox: Boolean(SONIOX_API_KEY),
    anthropic: Boolean(process.env.ANTHROPIC_API_KEY),
    model: LLM_MODEL,
  }),
);

app.listen(PORT, () => {
  console.log(`[ALFRED proxy] listening on http://localhost:${PORT}`);
  if (!process.env.ANTHROPIC_API_KEY) console.warn('  ⚠ ANTHROPIC_API_KEY not set');
  if (!SONIOX_API_KEY) console.warn('  ⚠ SONIOX_API_KEY not set');
});
