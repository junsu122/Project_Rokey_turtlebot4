/**
 * Emergency detections raised by the robot's on-patrol vision (YOLO) and pushed
 * to the kiosk over the ROS bridge (requirement ver03). Each maps to a
 * full-screen alert (emoji + siren + TTS) — see features/alerts.
 *
 * This is the pure domain type. Presentation (emoji/text/sound) lives in
 * features/alerts/alerts.config.ts; transport (which ROS topic, message shape)
 * lives in services/detection. The Vision/Driving track plugs into those two
 * seams without touching the UI.
 */
export type DetectionType = 'FIRE' | 'INJURED' | 'SUSPICIOUS';

export const DETECTION_TYPES: readonly DetectionType[] = [
  'FIRE',
  'INJURED',
  'SUSPICIOUS',
];

/** Keyword → DetectionType, tolerant of the wire label the robot ends up using. */
const DETECTION_ALIASES: Record<DetectionType, readonly string[]> = {
  FIRE: ['fire', 'flame', '화재', '불'],
  INJURED: ['injured', 'injury', 'patient', 'fallen', '부상', '부상자', '환자'],
  SUSPICIOUS: [
    'suspicious',
    'suspicious_person',
    'intruder',
    '거동수상',
    '거동수상자',
    '수상',
  ],
};

/**
 * Best-effort map an arbitrary label (or topic name) to a DetectionType — case-
 * and substring-insensitive. Returns null if nothing matches. This is the single
 * place to adjust when the robot's actual detection labels are finalized.
 */
export function parseDetectionLabel(label: string): DetectionType | null {
  const s = label.trim().toLowerCase();
  if (!s) return null;
  // Exact enum first (e.g. 'FIRE'), then alias substring match.
  for (const type of DETECTION_TYPES) {
    if (s === type.toLowerCase()) return type;
  }
  for (const type of DETECTION_TYPES) {
    if (DETECTION_ALIASES[type].some((alias) => s.includes(alias))) return type;
  }
  return null;
}
