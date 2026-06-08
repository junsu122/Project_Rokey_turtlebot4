import type { Facility, NavigationPlan } from '@/core/domain';
import { makeId } from '@/core/utils/id';
import type { RosGoal, RosService } from '../ros';
import type {
  NavigationHandle,
  NavigationHandlers,
  NavigationService,
} from './NavigationService';

export interface MockNavigationDeps {
  ros: RosService;
  /** Transfer points on a floor, ordered by preference (elevator first). */
  getTransferPoints: (floorId: string) => Facility[];
  /** Simulated time to escort one leg. */
  travelMs: number;
  /** Simulated time the next-floor robot takes to take over. */
  handoffMs: number;
}

const PROGRESS_STEPS = 20;

/**
 * Simulated escort. Publishes (mock) ROS goals and emits progress with the same
 * phases a real robot would report. For cross-floor trips it drives to the
 * transfer point, asks the other robot to take over, then completes (#6).
 */
export class MockNavigationService implements NavigationService {
  constructor(private readonly deps: MockNavigationDeps) {}

  planRoute(destination: Facility, originFloorId: string): NavigationPlan {
    const id = makeId('nav');

    if (destination.floorId === originFloorId) {
      return { id, destination, originFloorId, kind: 'same-floor' };
    }

    const via = this.deps.getTransferPoints(originFloorId)[0];
    return {
      id,
      destination,
      originFloorId,
      kind: 'cross-floor',
      transfer: via
        ? { via, fromFloorId: originFloorId, toFloorId: destination.floorId }
        : undefined,
    };
  }

  start(plan: NavigationPlan, handlers: NavigationHandlers): NavigationHandle {
    const timers: number[] = [];
    let cancelled = false;
    const clearAll = () => timers.forEach((t) => window.clearTimeout(t));
    const after = (ms: number, fn: () => void) => {
      timers.push(
        window.setTimeout(() => {
          if (!cancelled) fn();
        }, ms),
      );
    };

    // First leg target: the transfer point (cross-floor) or the destination.
    const firstTarget =
      plan.kind === 'cross-floor' && plan.transfer
        ? plan.transfer.via
        : plan.destination;

    handlers.onProgress({ phase: 'starting', ratio: 0 });
    void this.deps.ros.publishGoal(toGoal(firstTarget, plan.originFloorId));

    for (let step = 1; step <= PROGRESS_STEPS; step += 1) {
      after((this.deps.travelMs / PROGRESS_STEPS) * step, () =>
        handlers.onProgress({ phase: 'moving', ratio: step / PROGRESS_STEPS }),
      );
    }

    if (plan.kind === 'same-floor' || !plan.transfer) {
      after(this.deps.travelMs + 60, () =>
        handlers.onProgress({ phase: 'arrived', ratio: 1 }),
      );
    } else {
      const { transfer, destination } = plan;
      after(this.deps.travelMs + 60, () => {
        handlers.onProgress({ phase: 'awaiting-handoff', ratio: 1 });
        void this.deps.ros.requestHandoff(
          transfer.toFloorId,
          toGoal(destination, destination.floorId),
        );
      });
      after(this.deps.travelMs + this.deps.handoffMs + 60, () =>
        handlers.onProgress({ phase: 'arrived', ratio: 1 }),
      );
    }

    return {
      cancel: () => {
        if (cancelled) return;
        cancelled = true;
        clearAll();
        void this.deps.ros.cancelGoal();
        handlers.onProgress({ phase: 'cancelled', ratio: 0 });
      },
    };
  }
}

function toGoal(facility: Facility, floorId: string): RosGoal {
  // Prefer the real map-frame pose (meters); fall back to blueprint units.
  const pose = facility.pose ?? facility.position;
  return {
    facilityId: facility.id,
    facilityName: facility.name,
    floorId,
    x: pose.x,
    y: pose.y,
  };
}
