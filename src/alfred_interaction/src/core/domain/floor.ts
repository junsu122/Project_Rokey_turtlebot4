/**
 * A floor / separated space of the station (requirement situation #5).
 * Each floor has one robot and one schematic blueprint.
 */

/** A rectangular room/area drawn on the blueprint (units = blueprint units). */
export interface BlueprintRoom {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
  /** Visual emphasis: 'room' (outlined) | 'zone' (subtle fill). */
  kind?: 'room' | 'zone';
}

/** A polyline/wall drawn on the blueprint (units = blueprint units). */
export interface BlueprintWall {
  id: string;
  points: Array<[number, number]>;
  closed?: boolean;
}

/** A non-interactive decoration drawn on the blueprint (e.g. a train car). */
export interface BlueprintDecoration {
  id: string;
  kind: 'train';
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Floor {
  id: string;
  /** "1층" */
  name: string;
  /** "1F" */
  shortName: string;
  /** Numeric floor used on the wire (IF-01 destination/origin `floor`). */
  level: number;
  /** Outer boundary rectangle of the drawable area. */
  outline: BlueprintRoom;
  rooms: BlueprintRoom[];
  walls?: BlueprintWall[];
  decorations?: BlueprintDecoration[];
}
