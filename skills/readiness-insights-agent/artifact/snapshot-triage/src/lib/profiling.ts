import type { ColumnMap, ColumnProfile, DimKey, Scale, Table } from "./types";
import { DIMS, REVERSE_HINTS } from "./dimensions";

export function profile(table: Table): ColumnProfile[] {
  return table.header.map((name, i) => {
    const values = table.body.map((r) => r[i]).filter((v) => v !== "");
    const nums = values.map(Number).filter((v) => Number.isFinite(v));
    const numeric = values.length > 0 && nums.length / values.length > 0.85;
    const distinctSet = new Set(values);
    const avgLen = values.length ? values.reduce((a, v) => a + v.length, 0) / values.length : 0;
    const min = nums.length ? Math.min(...nums) : null;
    const max = nums.length ? Math.max(...nums) : null;
    return {
      index: i,
      name,
      values,
      nums,
      numeric,
      distinct: distinctSet.size,
      distinctValues: [...distinctSet].slice(0, 14),
      avgLen,
      min,
      max,
      sample: values[0] ?? "",
    };
  });
}

function guessScale(p: ColumnProfile): Scale | null {
  if (!p.numeric || p.min === null || p.max === null) return null;
  if (p.min >= 0 && p.max <= 5 && p.distinct <= 8) return p.min === 0 ? { min: 0, max: 5 } : { min: 1, max: 5 };
  if (p.min >= 1 && p.max <= 7 && p.distinct <= 9) return { min: 1, max: 7 };
  if (p.min >= 0 && p.max <= 10 && p.distinct <= 12) return { min: 0, max: 10 };
  if (p.min >= 0 && p.max <= 100 && p.distinct > 12) return { min: 0, max: 100 };
  return null;
}

function guessDimension(name: string): { dimension: DimKey; matched: boolean } {
  const h = name.toLowerCase();
  let best: DimKey | null = null;
  let bestAt = Infinity;
  for (const [key, , words] of DIMS) {
    for (const w of words) {
      const at = h.indexOf(w);
      if (at >= 0 && at < bestAt) {
        best = key;
        bestAt = at;
      }
    }
  }
  return { dimension: best ?? "understanding", matched: best !== null };
}

const looksReversed = (name: string) => REVERSE_HINTS.some((w) => name.toLowerCase().includes(w));

/**
 * Guesses one column mapping per profile, then keeps only the single most
 * plausible "segment" candidate — one grouping column drives the matrix, so
 * the rest are proposed as ignored rather than silently all applied.
 */
export function guessRoles(profiles: ColumnProfile[], rowCount: number): ColumnMap[] {
  const guessed: ColumnMap[] = profiles.map((p) => {
    const scale = guessScale(p);
    const g = guessDimension(p.name);
    const base = {
      name: p.name,
      scale: scale ?? { min: 1, max: 5 },
      dimension: g.dimension,
      unmatched: !g.matched,
      reverse: false,
    };
    const nameish = /^(id|ref|response|respondent|submitted|date|timestamp|email|name)\b/i.test(p.name);
    if (nameish) return { ...base, role: "ignore" };
    if (p.numeric && scale && scale.max <= 10 && p.distinct > 1) {
      return { ...base, role: "score", reverse: looksReversed(p.name) };
    }
    if (!p.numeric && p.avgLen > 25) return { ...base, role: "comment" };
    if (!p.numeric && p.distinct >= 2 && p.distinct <= Math.max(12, rowCount * 0.25) && p.avgLen <= 40) {
      return { ...base, role: "segment" };
    }
    return { ...base, role: "ignore" };
  });

  const candidates = guessed
    .map((m, i) => ({ m, i }))
    .filter((x) => x.m.role === "segment");
  if (candidates.length > 1) {
    const best = candidates.reduce((a, b) =>
      Math.abs(profiles[b.i].distinct - 4) < Math.abs(profiles[a.i].distinct - 4) ? b : a,
    );
    for (const c of candidates) if (c.i !== best.i) c.m.role = "ignore";
  }
  return guessed;
}

export const SCALE_PRESETS: [string, Scale][] = [
  ["1-5", { min: 1, max: 5 }],
  ["0-5", { min: 0, max: 5 }],
  ["1-7", { min: 1, max: 7 }],
  ["1-10", { min: 1, max: 10 }],
  ["0-10", { min: 0, max: 10 }],
  ["0-100", { min: 0, max: 100 }],
];
