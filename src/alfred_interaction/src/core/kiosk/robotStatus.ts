import type { DetectionType } from '@/core/domain';
import type { KioskEvent } from './types';

/**
 * Inbound robot state strings (IF-02) published by the robot over ros_bridge
 * (e.g. on `/robotN/ui_state`). The transport parses each message into a
 * RobotStatusMessage and feeds it to `robotStatusToEvent`.
 */
export type RobotStatus =
  | 'ESCORT_1F'
  | 'ESCORT_2F'
  | 'WAITING_1F'
  | 'WAITING_2F'
  | 'ESCORT_1F_FINISHED'
  | 'ESCORT_2F_FINISHED'
  | 'ESCORT_COMPLETED'
  | 'DOCKING'
  | 'UNDOCKING'
  | 'PATROL'
  | 'FIRE'
  | 'INJURED'
  | 'SUSPICIOUS';

/** A parsed robot status message (the JSON the robot sends, normalized). */
export interface RobotStatusMessage {
  /** Required — the status string (drives the screen). */
  state: string;
  /** Which robot reported it (robot2 / robot4). */
  robotId?: string;
  /** ESCORT_*: where we're escorting to. */
  destination?: { poiId?: string; name?: string };
  /** ESCORT_*_FINISHED: floor (1/2) the user should move to. */
  targetFloor?: number;
  /** DOCKING/UNDOCKING: charge level 0..100. */
  battery?: number;
  /** ESCORT_*: progress 0..1. */
  progress?: number;
  timestamp?: string;
}

/**
 * Map a parsed robot status → the kiosk event that shows the matching screen.
 *
 * Returns `null` for ESCORT_1F/2F: those need the destination NAME resolved
 * (config + language), which the RobotStateProvider does before dispatching
 * ROBOT_ESCORT. Every other status maps here.
 */
export function robotStatusToEvent(msg: RobotStatusMessage): KioskEvent | null {
  switch (msg.state) {
    case 'DOCKING':
    case 'UNDOCKING':
      return { type: 'ENTER_CHARGING', battery: msg.battery };

    case 'WAITING_1F':
    case 'WAITING_2F':
      return { type: 'ENTER_WAITING', info: { kind: 'waiting' } };

    // Done on this floor → send the user to the other floor. Prefer the floor
    // the robot names (target_floor); else fall back by which floor finished.
    case 'ESCORT_1F_FINISHED':
      return {
        type: 'ENTER_WAITING',
        info: { kind: 'transfer', toFloorId: floorId(msg.targetFloor, 'F2') },
      };
    case 'ESCORT_2F_FINISHED':
      return {
        type: 'ENTER_WAITING',
        info: { kind: 'transfer', toFloorId: floorId(msg.targetFloor, 'F1') },
      };

    case 'ESCORT_COMPLETED':
      return { type: 'END_GUIDING' }; // final arrival → back to patrol

    case 'PATROL':
      return { type: 'EXIT_ROBOT_SCREEN' };

    case 'FIRE':
    case 'INJURED':
    case 'SUSPICIOUS':
      return { type: 'DETECTION', detection: msg.state as DetectionType };

    case 'ESCORT_1F':
    case 'ESCORT_2F':
      return null; // provider resolves destination name → dispatches ROBOT_ESCORT

    default:
      return null;
  }
}

/** 1 → 'F1', 2 → 'F2', else the fallback floor id. */
function floorId(targetFloor: number | undefined, fallback: string): string {
  return targetFloor === 1 ? 'F1' : targetFloor === 2 ? 'F2' : fallback;
}
