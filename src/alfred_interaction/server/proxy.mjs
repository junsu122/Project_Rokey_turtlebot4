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
import { mkdir, writeFile, appendFile } from 'node:fs/promises';
import path from 'node:path';
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
// Claude가 이 zod 스키마에 "강제로" 맞춰 답하게 함 → 파싱 실패 없이 구조화된 결과를 받음.
const Understanding = z.object({
  intent: z.enum(['facility', 'chat']),        // 시설 안내 요청인가 / 일반 대화인가
  poi_id: z.string().nullable(),               // facility면 최적 POI id, 아니면 null
  confidence: z.number(),                      // 시설 매칭 확신도 0~1 (chat이면 0)
  reply: z.string(),                           // 사용자에게 보여줄 짧은 응답(감지된 언어로)
  language: z.enum(['ko', 'en', 'ja', 'zh']),  // 사용자가 실제로 말한 언어
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

// 음성 이해 엔드포인트: 브라우저가 STT 결과(transcript)+후보 시설(candidates)을 보내면
// Claude가 의도/POI/응답을 구조화해 돌려준다. (API 키는 서버에만 — 브라우저는 /api로만 호출)
app.post('/api/llm/understand', async (req, res) => {
  try {
    const { transcript, language, candidates } = req.body ?? {};
    if (typeof transcript !== 'string' || !transcript.trim()) {
      return res.status(400).json({ error: 'transcript required' });   // 빈 입력 거부
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

    // 공식 SDK + 구조화 출력(zodOutputFormat): 모델이 Understanding 스키마에 맞춰 응답.
    const message = await anthropic.messages.parse({
      model: LLM_MODEL,                 // 기본 claude-haiku-4-5 (빠르고 저렴)
      max_tokens: 1024,
      system: SYSTEM_PROMPT,            // 시설/대화 판정 규칙 + 언어 감지 지시
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
    // 키 무효(401)·API 오류를 구분해서 내려보냄 → 브라우저 로그만 봐도 원인 파악 가능
    if (err instanceof Anthropic.AuthenticationError) {
      return res.status(502).json({
        error: 'anthropic_auth_failed',
        hint: 'ANTHROPIC_API_KEY가 유효하지 않습니다. .env 갱신 후 proxy 재시작 필요',
      });
    }
    if (err instanceof Anthropic.APIError) {
      return res
        .status(502)
        .json({ error: 'anthropic_api_error', status: err.status });
    }
    return res.status(500).json({ error: 'llm_failed' });
  }
});

// Soniox 임시키 발급: 브라우저가 stt-rt-v4 WebSocket을 열려면 키가 필요한데, 영구키를
// 브라우저로 내려보낼 수 없으므로 여기서 단기(기본 300초) 임시키를 받아 그것만 전달한다.
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

// 헬스체크: 브라우저에서 http://localhost:5173/api/health 로 키 설정 여부 확인용.
app.get('/api/health', (_req, res) =>
  res.json({
    ok: true,
    soniox: Boolean(SONIOX_API_KEY),                    // 임시키 발급 가능?
    anthropic: Boolean(process.env.ANTHROPIC_API_KEY),  // LLM 호출 가능?
    model: LLM_MODEL,
  }),
);

// UI 콘솔 로그 기록(개발용): 브라우저 console 출력을 logs/ui-console.txt 에 적재.
// reset=true(세션 첫 전송)면 파일을 새로 쓰고, 이후엔 append. (cwd = alfred_interaction/)
const LOG_FILE = path.join(process.cwd(), 'logs', 'ui-console.txt');
app.post('/api/log', async (req, res) => {
  try {
    const { lines, reset } = req.body ?? {};
    if (!Array.isArray(lines)) {
      return res.status(400).json({ error: 'lines[] required' });
    }
    await mkdir(path.dirname(LOG_FILE), { recursive: true });
    const text = lines.join('\n') + '\n';
    await (reset ? writeFile(LOG_FILE, text) : appendFile(LOG_FILE, text));
    return res.json({ ok: true });
  } catch (err) {
    console.error('[log] error', err);
    return res.status(500).json({ error: 'log_failed' });
  }
});

app.listen(PORT, () => {
  console.log(`[ALFRED proxy] listening on http://localhost:${PORT}`);
  if (!process.env.ANTHROPIC_API_KEY) console.warn('  ⚠ ANTHROPIC_API_KEY not set');
  if (!SONIOX_API_KEY) console.warn('  ⚠ SONIOX_API_KEY not set');
});
