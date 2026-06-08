import type { Floor } from '@/core/domain';

/**
 * Shared blueprint coordinate space. Room & facility coordinates are expressed
 * in these units; the SVG viewBox is "-10 0 170 100". The negative `minX`
 * leaves room on the left for the train, which is parked outside the building
 * outline (x=8) alongside the boarding platforms.
 */
export const BLUEPRINT = { minX: -10, width: 170, height: 100 } as const;

const outline = {
  id: 'outline',
  x: 8,
  y: 10,
  w: 144,
  h: 80,
} as const;

/**
 * Two separated spaces (situation #5), modeled after the real station section
 * drawings. The actual fixtures (restroom, gates, benches, elevator, …) are
 * drawn from the facility footprints in facilities.ts — here we only define the
 * outer shell plus a couple of structural walls.
 */
export const floors: Floor[] = [
  {
    id: 'F1',
    name: '1층',
    shortName: '1F',
    level: 1,
    outline: { ...outline },
    rooms: [],
    walls: [],
  },
  {
    id: 'F2',
    name: '2층',
    shortName: '2F',
    level: 2,
    outline: { ...outline },
    rooms: [],
    walls: [
      // Divider between the boarding platforms (left) and the concourse,
      // continuing into the fare-gate line. The line is solid (a wall) except
      // at the two ticket gates (the gaps at x66–88 and x116–146).
      { id: 'f2-div', points: [[9, 66], [34, 66]] },
      { id: 'f2-fare-mid', points: [[56, 66], [86, 66]] },
      { id: 'f2-fare-right', points: [[116, 66], [152, 66]] },
    ],
    decorations: [
      // The actual train, to the LEFT of platforms A-1/A-2/A-3.
      { id: 'f2-train', kind: 'train', x: -7, y: 11, w: 14, h: 45 },
    ],
  },
];
