import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { env } from '@/config';
import { initConsoleCapture } from '@/core/log/consoleCapture';
import { App } from '@/app/App';

import '@/styles/tokens.css';
import '@/styles/global.css';

// F12 콘솔 로그 캡처: dev 에선 프록시(/api/log)로 보내 logs/ui-console.txt 에 자동 기록,
// 어느 모드에서나 window.alfredSaveLog() 로 .txt 다운로드. (앱 렌더 전에 시작해 전부 캡처)
initConsoleCapture({ apiBase: import.meta.env.DEV ? env.apiBase : null });

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root container #root not found in index.html');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
