// .81 rosbridge 에 붙어 /robot2/robot_state 토픽 JSON 을 받는 최소 클라이언트.
// 추가 설치 불필요 — Node 22+ 의 내장 WebSocket 사용 (이 노트북은 v24).
//
// 실행:  node ws-robot-state.mjs
// 종료:  Ctrl + C
//
// WINDOWS_CLAUDE_HANDOFF.md 의 요청 그대로:
//   subscribe → {"op":"subscribe","topic":"/robot2/robot_state","type":"alfred_interfaces/msg/RobotState"}
//   수신      → {"op":"publish","topic":"/robot2/robot_state","msg":{ ...RobotState... }}

const URL = 'ws://192.168.107.81:9090';
const TOPIC = '/escort_state';
const TYPE = 'alfred_interfaces/msg/RobotState';

console.log(`[connecting] ${URL} ...`);
const ws = new WebSocket(URL);

ws.addEventListener('open', () => {
  console.log(`[open] connected → ${URL}`);
  ws.send(JSON.stringify({ op: 'subscribe', topic: TOPIC, type: TYPE }));
  console.log(`[subscribe] ${TOPIC} (${TYPE}) — 메시지 기다리는 중...`);
});

ws.addEventListener('message', (ev) => {
  let f;
  try {
    f = JSON.parse(ev.data);
  } catch {
    console.log('[raw]', ev.data);
    return;
  }
  if (f.op === 'status') {
    // rosbridge 쪽 에러/경고 (예: alfred_interfaces 미소싱 → 타입 import 실패)
    console.warn(`[status:${f.level}] ${f.msg}`);
  } else if (f.op === 'publish') {
    console.log(`[${f.topic}]`, JSON.stringify(f.msg)); // ← 실제 RobotState
  } else {
    console.log('[other]', f);
  }
});

ws.addEventListener('error', (e) => {
  console.error('[error]', e?.message ?? e);
  console.error('  → .81 서버가 안 떠 있거나 방화벽/네트워크 문제일 수 있음');
});

ws.addEventListener('close', (e) => {
  console.warn(`[close] code=${e.code} reason=${e.reason || '(none)'}`);
});
