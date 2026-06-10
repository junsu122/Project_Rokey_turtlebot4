/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Which floor this Alfred serves: '1' or '2' (also accepts 'F1'/'F2'). */
  readonly VITE_FLOOR?: string;
  /** Default UI/voice language: 'ko' | 'en' | 'ja' | 'zh'. */
  readonly VITE_DEFAULT_LANG?: string;
  /** 'true' to force the mock STT/LLM services (offline dev). */
  readonly VITE_USE_MOCKS?: string;
  /** Base URL of the backend proxy (Soniox temp key + Claude). Default '/api'. */
  readonly VITE_API_BASE?: string;
  /** Soniox real-time model id. Default 'stt-rt-v4'. */
  readonly VITE_SONIOX_MODEL?: string;
  /** rosbridge host — just the IP, e.g. '192.168.107.41'. Change this when it moves. Empty = mock FMS. */
  readonly VITE_ROSBRIDGE_HOST?: string;
  /** rosbridge port. Default '9090'. */
  readonly VITE_ROSBRIDGE_PORT?: string;
  /** Full rosbridge URL override (wins over HOST/PORT), e.g. 'ws://192.168.107.41:9090'. */
  readonly VITE_ROSBRIDGE_URL?: string;
  /** ROS topic(s) for YOLO emergency detections, comma-separated. Default '/detection'. */
  readonly VITE_DETECTION_TOPIC?: string;
  /** ROS topic for this robot's UI status. Empty = derived '/<robotId>/ui_state'. */
  readonly VITE_ROBOT_STATE_TOPIC?: string;
  /** ROS topic for IF-01 customer requests. Default '/information'. */
  readonly VITE_ROS_INFO_TOPIC?: string;
  /** ROS message type to advertise for the info topic. Empty = publish only. */
  readonly VITE_ROS_INFO_MSG_TYPE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
