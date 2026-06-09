let counter = 0;

/** Small, dependency-free unique id generator for sessions/plans. */
export function makeId(prefix = 'id'): string {
  counter += 1;
  const rand =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10);
  return `${prefix}_${counter}_${rand}`;
}
