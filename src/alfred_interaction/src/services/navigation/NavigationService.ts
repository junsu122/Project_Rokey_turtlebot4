import type { Facility, NavigationPlan, NavigationProgress } from '@/core/domain';

/**
 * Escort orchestration contract. Turns a chosen facility into a route plan and
 * drives it (publishing ROS goals, handling the cross-floor handoff in #6),
 * reporting progress back to the UI.
 */
export interface NavigationHandlers {
  onProgress: (progress: NavigationProgress) => void;
}

export interface NavigationHandle {
  cancel(): void;
}

export interface NavigationService {
  /** Decide same-floor vs cross-floor (and which transfer point) for a target. */
  planRoute(destination: Facility, originFloorId: string): NavigationPlan;

  /** Begin executing a plan; returns a handle to cancel it. */
  start(plan: NavigationPlan, handlers: NavigationHandlers): NavigationHandle;
}
