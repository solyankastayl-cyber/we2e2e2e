/**
 * Phase 7.8-7.9: Archive Utilities
 */

import { YearMonth } from "./archive.types.js";

export function monthsBetween(
  startYear: number,
  startMonth: number,
  endYear: number,
  endMonth: number
): YearMonth[] {
  const out: YearMonth[] = [];
  let y = startYear;
  let m = startMonth;

  while (y < endYear || (y === endYear && m <= endMonth)) {
    out.push({ year: y, month: m });
    m++;
    if (m > 12) {
      m = 1;
      y++;
    }
  }
  return out;
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
