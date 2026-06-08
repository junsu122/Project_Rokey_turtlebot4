import type { FacilityCategory } from '@/core/domain';

/** Category → glyph. Shared by <FacilityIcon> and the SVG blueprint markers. */
export const FACILITY_GLYPHS: Record<FacilityCategory, string> = {
  restroom: '🚻',
  office: '🏢',
  exit: '🚪',
  ticket: '🎫',
  info: 'ℹ️',
  gate: '🚇',
  convenience: '🏪',
  storage: '🛅',
  elevator: '🛗',
  escalator: '⤴️',
  stairs: '🪜',
  bench: '🪑',
  platform: '🚉',
  transit: '🔁',
};

export function facilityGlyph(category: FacilityCategory): string {
  return FACILITY_GLYPHS[category];
}

interface FacilityIconProps {
  category: FacilityCategory;
  className?: string;
}

/** Maps a facility category to a glyph. Size is controlled by the caller. */
export function FacilityIcon({ category, className }: FacilityIconProps) {
  return (
    <span className={className} role="img" aria-hidden="true">
      {FACILITY_GLYPHS[category]}
    </span>
  );
}
