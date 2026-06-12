import { DEFAULT_LANGUAGE, isLanguage, type Language } from '@/core/i18n';

/**
 * Build-time configuration from Vite env vars. Each Alfred (1F / 2F) is a
 * separate build that sets VITE_FLOOR; the backend proxy URL and language
 * default come from here too. See .env.example.
 */
function str(value: string | undefined, fallback: string): string {
  return value && value.length > 0 ? value : fallback;
}

function num(value: string | undefined, fallback: number): number {
  const n = Number(value);
  return value !== undefined && value !== '' && Number.isFinite(n)
    ? n
    : fallback;
}

const floorRaw = str(import.meta.env.VITE_FLOOR, '1')
  .toUpperCase()
  .replace('F', '');

const defaultLang = import.meta.env.VITE_DEFAULT_LANG;

// rosbridge target — change ONLY the IP via VITE_ROSBRIDGE_HOST and the whole
// ws:// URL follows. A full VITE_ROSBRIDGE_URL (advanced: custom scheme/port)
// overrides host+port. Empty host (and no override) → mock FMS.
const rosbridgeHost = str(import.meta.env.VITE_ROSBRIDGE_HOST, '').trim();
const rosbridgePort = str(import.meta.env.VITE_ROSBRIDGE_PORT, '9090').trim();
const rosbridgeUrlOverride = str(import.meta.env.VITE_ROSBRIDGE_URL, '')
  .trim()
  .replace(/\/$/, '');
const rosbridgeUrl =
  rosbridgeUrlOverride ||
  (rosbridgeHost ? `ws://${rosbridgeHost}:${rosbridgePort}` : '');

/** Force mocks (no API keys / proxy needed) — for offline dev. */
const useMocks = import.meta.env.VITE_USE_MOCKS === 'true';

/**
 * Mock-robot demo (VITE_MOCK_ROBOT=true): wire the FMS/robot-state mocks to an
 * in-memory fake robot so the full IF-01 ↔ ui_state escort round-trip runs with
 * NO rosbridge / robot. Independent of useMocks (STT/LLM); combine both for a
 * fully offline demo.
 */
const mockRobot = import.meta.env.VITE_MOCK_ROBOT === 'true';

export const env = {
  /** 1 or 2 — which floor this kiosk's robot serves. */
  floorNumber: floorRaw === '2' ? 2 : 1,
  /** Default UI/voice language. */
  defaultLanguage: (isLanguage(defaultLang)
    ? defaultLang
    : DEFAULT_LANGUAGE) as Language,
  /** Force mocks (no API keys / proxy needed) — for offline dev. */
  useMocks,
  /** Mock-robot demo: fake robot answers IF-01 with ui_state (no rosbridge/robot). */
  mockRobot,
  /** Backend proxy base (holds Soniox + Anthropic keys). */
  apiBase: str(import.meta.env.VITE_API_BASE, '/api').replace(/\/$/, ''),
  /** Soniox real-time model. */
  sonioxModel: str(import.meta.env.VITE_SONIOX_MODEL, 'stt-rt-v4'),
  /**
   * rosbridge_websocket URL of the laptop wired to the Turtlebot4. Built from
   * VITE_ROSBRIDGE_HOST (just the IP — change this one value when it moves) +
   * VITE_ROSBRIDGE_PORT, unless a full VITE_ROSBRIDGE_URL override is set.
   * Empty → mock FMS (console only).
   */
  rosbridgeUrl,
  /**
   * True when an external state source drives this kiosk via inbound ui_state —
   * a real robot (rosbridge live + mocks off) OR the mock-robot demo. The local
   * escort simulation is then suppressed so inbound state owns the guiding screen.
   */
  robotDrivesUi: mockRobot || (!useMocks && !!rosbridgeUrl),
  /** ROS topic carrying IF-01 customer requests (정의서 IF-01). */
  rosInfoTopic: str(import.meta.env.VITE_ROS_INFO_TOPIC, '/information'),
  /**
   * ROS message type advertised for the info topic so rosbridge can create the
   * publisher. Default std_msgs/String carries the IF-01 JSON as text (works
   * with no custom .msg on the robot). Point at a custom type (e.g.
   * 'alfred_msgs/Information') to send the structured fields instead.
   */
  rosInfoMsgType: str(import.meta.env.VITE_ROS_INFO_MSG_TYPE, 'std_msgs/String'),
  /**
   * ROS topic(s) carrying YOLO emergency detections (FIRE / INJURED /
   * SUSPICIOUS), comma-separated. The kiosk subscribes and raises a full-screen
   * alert (requirement ver03). e.g. '/detection' or '/yolo/fire,/yolo/intruder'.
   */
  detectionTopics: str(import.meta.env.VITE_DETECTION_TOPIC, '/detection')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean),
  /**
   * ROS topic carrying THIS robot's UI status (IF-02: ESCORT_1F / WAITING_1F /
   * DOCKING / PATROL …). Empty → derived from the robot id in createServices
   * (`/<robotId>/ui_state`, e.g. /robot2/ui_state). Set to override.
   */
  robotStateTopic: str(import.meta.env.VITE_ROBOT_STATE_TOPIC, ''),
  /**
   * ROS topic carrying THIS robot's live pose (m) for the map "현위치" dot
   * ({robot_id,x,y,theta}). Empty → derived from the robot id in createServices
   * (`/<robotId>/interacting_pose`). Set to override.
   */
  robotPoseTopic: str(import.meta.env.VITE_ROBOT_POSE_TOPIC, ''),
  /**
   * Mic noise-gate threshold in dBFS — input quieter than this is muted before
   * STT, cutting far/background voices. Lower = more permissive (e.g. -90 ≈ off);
   * raise toward -35 to gate more aggressively. Tune per mic/room.
   */
  micGateDb: num(import.meta.env.VITE_MIC_GATE_DB, -45),
  /** Log measured mic level for tuning the gate (defaults on in dev builds). */
  micGateDebug:
    import.meta.env.VITE_MIC_GATE_DEBUG !== undefined
      ? import.meta.env.VITE_MIC_GATE_DEBUG === 'true'
      : import.meta.env.DEV,
} as const;
