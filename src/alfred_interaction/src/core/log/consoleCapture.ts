/**
 * 콘솔 캡처 — F12 콘솔 출력을 그대로 두면서(여전히 F12에 보임) 메모리 버퍼에 기록하고:
 *   1) window.alfredSaveLog() 로 .txt 다운로드 (어느 모드에서나)
 *   2) (옵션) 프록시 /api/log 로 보내 logs/ui-console.txt 에 자동 기록 (dev)
 *
 * best-effort 설계 — 프록시가 안 떠 있으면 전송은 조용히 실패하고 다운로드만 동작한다.
 * 캡처 로직은 절대 앱을 깨지 않도록 try/catch로 감싼다.
 */
type Level = 'log' | 'info' | 'warn' | 'error' | 'debug';
const LEVELS: Level[] = ['log', 'info', 'warn', 'error', 'debug'];
const MAX_BUFFER = 5000;

let installed = false;
const buffer: string[] = [];
let pending: string[] = [];
let flushTimer: number | null = null;
let postUrl: string | null = null;
let sessionReset = true; // 첫 전송은 파일을 새로 씀(이전 세션 로그 덮어쓰기)

function stamp(): string {
  const d = new Date();
  const p = (n: number, len = 2) => String(n).padStart(len, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}

/** 인자 하나를 사람이 읽을 문자열로(문자열 그대로 / Error는 stack / 객체는 JSON). */
function part(a: unknown): string {
  if (typeof a === 'string') return a;
  if (a instanceof Error) return a.stack || `${a.name}: ${a.message}`;
  try {
    return JSON.stringify(a);
  } catch {
    return String(a);
  }
}

function record(level: Level, args: unknown[]): void {
  const line = `[${stamp()}] ${level.toUpperCase().padEnd(5)} ${args.map(part).join(' ')}`;
  buffer.push(line);
  if (buffer.length > MAX_BUFFER) buffer.shift();
  if (postUrl) {
    pending.push(line);
    if (flushTimer === null) flushTimer = window.setTimeout(flush, 1000);
  }
}

function flush(): void {
  flushTimer = null;
  if (!postUrl || pending.length === 0) return;
  const lines = pending;
  pending = [];
  const reset = sessionReset;
  sessionReset = false;
  void fetch(postUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lines, reset }),
  }).catch(() => {
    /* 프록시 미가동 — 무시(다운로드는 그대로 가능) */
  });
}

function download(): void {
  const blob = new Blob([buffer.join('\n') + '\n'], {
    type: 'text/plain;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  const a = document.createElement('a');
  a.href = url;
  a.download = `alfred-console-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

export interface ConsoleCaptureOptions {
  /** 프록시 base (예: '/api') — 주면 /api/log 로 자동 기록. null이면 다운로드만. */
  apiBase?: string | null;
}

/** 콘솔 캡처 시작(앱 진입점에서 1회). */
export function initConsoleCapture(opts: ConsoleCaptureOptions = {}): void {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  postUrl = opts.apiBase ? `${opts.apiBase}/log` : null;

  for (const level of LEVELS) {
    const orig = console[level].bind(console);
    console[level] = (...args: unknown[]) => {
      orig(...args); // F12 콘솔 출력 유지
      try {
        record(level, args);
      } catch {
        /* 캡처가 앱을 깨면 안 됨 */
      }
    };
  }

  // 페이지 닫힐 때 남은 로그 마지막 전송(동기 beacon).
  window.addEventListener('beforeunload', () => {
    if (postUrl && pending.length > 0 && navigator.sendBeacon) {
      navigator.sendBeacon(
        postUrl,
        new Blob([JSON.stringify({ lines: pending, reset: sessionReset })], {
          type: 'application/json',
        }),
      );
    }
  });

  const w = window as unknown as {
    alfredSaveLog?: () => void;
    alfredClearLog?: () => void;
  };
  w.alfredSaveLog = download;
  w.alfredClearLog = () => {
    buffer.length = 0;
  };

  console.info(
    `[console-capture] 기록 시작${postUrl ? ` → ${postUrl} (logs/ui-console.txt)` : ''} · ` +
      'window.alfredSaveLog() 로 txt 다운로드',
  );
}
