import type { Analysis } from "./types";
import { DIMLABEL, BAND_GOOD, BAND_WARN, MIN_N, NEG_MAX, POS_MIN } from "./dimensions";
import { findings } from "./analysis";

const BANDWORD: Record<string, string> = {
  good: "On track",
  warn: "Watch",
  crit: "At risk",
  thin: "Thin base",
  none: "No data",
};

export function summaryCsv(a: Analysis): string {
  const rows: (string | number)[][] = [
    ["group", "dimension", "n", "mean_0_100", "band", "pct_negative", "pct_positive", "sources"],
  ];
  for (const row of a.matrix) {
    for (const c of row.cells) {
      rows.push([
        c.seg,
        DIMLABEL[c.dim],
        c.n,
        c.n ? (c.mean ?? 0).toFixed(1) : "",
        BANDWORD[c.band],
        c.n ? c.neg.toFixed(1) : "",
        c.n ? c.pos.toFixed(1) : "",
        Object.keys(c.bySource)
          .map((sid) => a.sources.find((s) => s.sid === sid)?.label ?? sid)
          .join("; "),
      ]);
    }
  }
  return rows
    .map((r) => r.map((v) => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v)).join(","))
    .join("\n");
}

export function fullJson(a: Analysis, alias: Record<string, string>): string {
  return JSON.stringify(
    {
      generated: new Date().toISOString(),
      sources: a.sources,
      conventions: {
        bands: { on_track: BAND_GOOD, watch: BAND_WARN },
        thin_base_under: MIN_N,
        negative_at_or_below: NEG_MAX,
        positive_at_or_above: POS_MIN,
        note: "Scores normalised to 0-100, higher is better. Conventions, not findings.",
      },
      group_aliases: alias,
      respondents: a.respondents,
      dropped_cells: a.dropped,
      matrix: a.matrix.flatMap((r) =>
        r.cells.map((c) => ({
          group: c.seg,
          dimension: DIMLABEL[c.dim],
          dimension_key: c.dim,
          n: c.n,
          mean: c.n ? +(c.mean ?? 0).toFixed(1) : null,
          band: BANDWORD[c.band],
          pct_negative: c.n ? +c.neg.toFixed(1) : null,
          pct_positive: c.n ? +c.pos.toFixed(1) : null,
          by_source: Object.fromEntries(
            Object.entries(c.bySource).map(([sid, v]) => [sid, { n: v.n, mean: +v.mean.toFixed(1) }]),
          ),
        })),
      ),
      blind_spots: a.blind.map((c) => ({ group: c.seg, dimension: DIMLABEL[c.dim], status: c.band, n: c.n })),
      observations: findings(a).map((f) => ({ kind: f.kind, tag: f.tag, title: f.title, detail: f.body, evidence: f.ev })),
      comments: a.comments.map((c) => ({
        ref: c.id,
        source: c.source,
        group: c.seg,
        dimension: DIMLABEL[c.dim],
        question: c.col,
        text: c.text,
      })),
    },
    null,
    2,
  );
}

export { BANDWORD };
