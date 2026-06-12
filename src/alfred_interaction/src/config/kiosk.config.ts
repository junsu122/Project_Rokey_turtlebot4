import type { Language } from '@/core/i18n';
import { env } from './env';

/**
 * Per-robot runtime configuration. Each Alfred (1F / 2F) is its own build that
 * sets VITE_FLOOR; everything floor-specific (which floor it serves, its FMS
 * robot_id, its base pose) is derived here so the two kiosks stay in sync
 * (requirement ver02 §2.1: separate 1F and 2F UIs).
 */
export interface KioskConfig {
  /** Station display name. */
  stationName: string;
  /** Robot / product name. */
  robotName: string;
  /** IF-01 `robot_id` — this kiosk's robot identity on the FMS channel. */
  robotId: string;
  /** Which floor THIS kiosk's robot serves. */
  currentFloorId: string;
  /**
   * Robot base/standby pose (meters) stamped on IF-01 `origin.pose`. A real
   * deployment fills this from live odometry; here it's the charging-bay pose.
   * Used for the VI(blind) wake-word flow — the robot meets the customer here.
   */
  originPose: { x: number; y: number };
  /**
   * IF-01 `origin.pose` for normal (touch 시설검색·음성검색) customers — the
   * kiosk-front pickup point, distinct from the blind flow's standby pose.
   */
  originPoseNormal: { x: number; y: number };
  /** Initial UI/voice language. */
  defaultLanguage: Language;

  /** Inactivity before returning to patrol (requirement #10, defensive). */
  idleTimeoutMs: number;

  /** Demo-only timings — these stand in for the real ROS/robot feedback. */
  simulatedTravelMs: number;
  simulatedHandoffMs: number;
  /** How long the "도착했어요!" message holds before returning to patrol. */
  arrivedHoldMs: number;

  /** Request browser Fullscreen on first interaction as a kiosk fallback. */
  requestFullscreen: boolean;
  /** Hide the mouse cursor (true touch kiosk). */
  hideCursor: boolean;
}

/** Floor-specific identity (matches the turtlebot POI table: F1=robot2, F2=robot4). */
const FLOOR_PROFILES = {
  1: {
    currentFloorId: 'F1',
    robotId: 'robot2',
    originPose: { x: -3.2, y: 2.12 },
    originPoseNormal: { x: -7.0, y: 2.12 },
  },
  2: {
    currentFloorId: 'F2',
    robotId: 'robot4',
    originPose: { x: -2.25, y: 3.0 },
    originPoseNormal: { x: -2.25, y: 3.0 },
  },
} as const;

const profile = FLOOR_PROFILES[env.floorNumber];

export const kioskConfig: KioskConfig = {
  stationName: '로키대학교역',
  robotName: 'ALFRED',
  robotId: profile.robotId,
  currentFloorId: profile.currentFloorId,
  originPose: { ...profile.originPose },
  originPoseNormal: { ...profile.originPoseNormal },
  defaultLanguage: env.defaultLanguage,

  idleTimeoutMs: 60_000,

  simulatedTravelMs: 6_000,
  simulatedHandoffMs: 3_000,
  arrivedHoldMs: 2_600,

  requestFullscreen: true,
  hideCursor: false,
};
