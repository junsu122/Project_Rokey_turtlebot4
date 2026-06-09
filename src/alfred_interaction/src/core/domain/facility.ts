import type { Language } from '@/core/i18n';

/**
 * A facility a user can be guided to (restroom, office, exit, transfer point...).
 * Pure domain type — no UI, no framework.
 */
export type FacilityCategory =
  | 'restroom'
  | 'office'
  | 'exit'
  | 'ticket'
  | 'info'
  | 'gate'
  | 'convenience'
  | 'storage'
  | 'elevator'
  | 'escalator'
  | 'stairs'
  | 'bench' // 벤치
  | 'platform' // 탑승구
  | 'transit'; // 환승

/** Coordinate in blueprint units (see BLUEPRINT in config/floors). */
export interface FacilityPosition {
  x: number;
  y: number;
}

/** Real-world goal pose in the robot map frame (meters), from the POI table. */
export interface FacilityPose {
  x: number;
  y: number;
}

/** Bounding box on the blueprint, used to draw a floor-plan-style fixture. */
export interface FacilityFootprint {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Facility {
  id: string;
  /** Display name in Korean (default / fallback), e.g. "화장실". */
  name: string;
  /** Localized display names (en/ja/zh). Falls back to `name` (ko). */
  i18n?: Partial<Record<Language, string>>;
  category: FacilityCategory;
  /** Which floor this facility physically lives on. */
  floorId: string;
  /**
   * FMS POI table id sent to the server as IF-01 `destination.poi_id`. Present
   * only on navigable destinations (display-only fixtures like benches omit it).
   */
  poiId?: string;
  /** Robot map-frame goal pose (meters) from the turtlebot POI table. */
  pose?: FacilityPose;
  /** Blueprint marker position (drawing only), in blueprint units. */
  position: FacilityPosition;
  /** Optional drawn footprint on the blueprint (floor-plan look). */
  footprint?: FacilityFootprint;
  /** Drawing sub-style, e.g. bench 'a'|'b', gate 'narrow'|'wide', 'door'. */
  variant?: string;
  /** Optional rotation (degrees, clockwise) applied to the drawn fixture. */
  rotation?: number;
  /** Alternative phrasings used for voice/LLM matching, e.g. ["변소", "토일렛"]. */
  aliases?: string[];
  /** Optional one-line description shown in the UI. */
  description?: string;
  /**
   * Whether the user can pick this as an escort destination. Defaults to true;
   * set false for orientation-only fixtures drawn on the map but never navigated
   * to (e.g. benches).
   */
  selectable?: boolean;
}

/** Vertical transfer points used to move between floors (requirement #6). */
export const TRANSFER_CATEGORIES: ReadonlyArray<FacilityCategory> = [
  'elevator',
  'escalator',
  'stairs',
];

export function isTransferFacility(facility: Facility): boolean {
  return TRANSFER_CATEGORIES.includes(facility.category);
}

/**
 * Whether a user can choose this facility as an escort destination. Display-only
 * fixtures (e.g. benches) set `selectable: false`; everything else defaults to
 * selectable.
 */
export function isSelectableFacility(facility: Facility): boolean {
  // Navigable only if it maps to a server POI id and isn't explicitly hidden.
  return facility.poiId != null && facility.selectable !== false;
}

/** Display name for a facility in the given language (falls back to Korean `name`). */
export function localizedFacilityName(
  facility: Facility,
  language: Language,
): string {
  return facility.i18n?.[language] ?? facility.name;
}
