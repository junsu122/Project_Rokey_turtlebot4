import type { Facility, Floor } from '@/core/domain';
import { TRANSFER_CATEGORIES } from '@/core/domain';
import { facilities } from './facilities';
import { floors } from './floors';

export { kioskConfig } from './kiosk.config';
export type { KioskConfig } from './kiosk.config';
export { env } from './env';
export { messages, useStrings } from './i18n';
export { facilities } from './facilities';
export { floors, BLUEPRINT } from './floors';

// ---- Lookups (kept here so features never index raw arrays themselves) ----

export function getFloor(floorId: string): Floor | undefined {
  return floors.find((f) => f.id === floorId);
}

export function getFloorOrThrow(floorId: string): Floor {
  const floor = getFloor(floorId);
  if (!floor) throw new Error(`Unknown floor: ${floorId}`);
  return floor;
}

/** Numeric floor (IF-01 `floor`) for a floor id, e.g. 'F1' → 1. */
export function floorLevel(floorId: string): number {
  return getFloorOrThrow(floorId).level;
}

export function getFacility(facilityId: string): Facility | undefined {
  return facilities.find((f) => f.id === facilityId);
}

export function getFacilityOrThrow(facilityId: string): Facility {
  const facility = getFacility(facilityId);
  if (!facility) throw new Error(`Unknown facility: ${facilityId}`);
  return facility;
}

/** Facility by its FMS POI id (IF-01/IF-02 `poi_id`), e.g. 'WC' → 화장실. */
export function getFacilityByPoiId(poiId: string): Facility | undefined {
  return facilities.find((f) => f.poiId === poiId);
}

export function facilitiesOnFloor(floorId: string): Facility[] {
  return facilities.filter((f) => f.floorId === floorId);
}

/**
 * Transfer points on a floor, ordered by escort preference
 * (elevator → escalator → stairs). Used to plan the cross-floor handoff (#6).
 */
export function transferPointsOnFloor(floorId: string): Facility[] {
  const order = TRANSFER_CATEGORIES;
  return facilities
    .filter((f) => f.floorId === floorId && order.includes(f.category))
    .sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category));
}

/** For a 2-floor station, the "other" floor relative to `floorId`. */
export function otherFloorId(floorId: string): string | undefined {
  return floors.find((f) => f.id !== floorId)?.id;
}
