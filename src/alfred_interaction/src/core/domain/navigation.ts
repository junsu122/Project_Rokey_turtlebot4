/**
 * Navigation domain — the plan a robot follows to escort a user to a facility,
 * including the multi-floor handoff case (requirement #6).
 */
import type { Facility } from './facility';

export type NavigationKind = 'same-floor' | 'cross-floor';

/**
 * The vertical move when a destination is on another floor.
 * `via` is the transfer point (elevator/escalator/stairs) on the ORIGIN floor.
 */
export interface TransferStep {
  via: Facility;
  fromFloorId: string;
  toFloorId: string;
}

export interface NavigationPlan {
  id: string;
  destination: Facility;
  originFloorId: string;
  kind: NavigationKind;
  /** Present only when kind === 'cross-floor'. */
  transfer?: TransferStep;
}

export type NavigationPhase =
  | 'starting'
  | 'moving' // escorting to destination (same floor) or to the transfer point
  | 'awaiting-handoff' // arrived at transfer point; next-floor robot taking over
  | 'arrived'
  | 'cancelled'
  | 'error';

export interface NavigationProgress {
  phase: NavigationPhase;
  /** 0..1 completion of the current leg. */
  ratio: number;
  message?: string;
}

/** A live escort session bound to the UI. */
export interface NavigationSession {
  plan: NavigationPlan;
  progress: NavigationProgress;
}

export const isTerminalPhase = (phase: NavigationPhase): boolean =>
  phase === 'arrived' || phase === 'cancelled' || phase === 'error';
