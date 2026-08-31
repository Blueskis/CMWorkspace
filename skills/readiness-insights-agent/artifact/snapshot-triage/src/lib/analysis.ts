import type { Analysis, Band, Cell, Comment, DimKey, Finding, Source } from "./types";
import { BAND_GOOD, BAND_WARN, DIMLABEL, DIM_ORDER, MIN_N, NEG_MAX, POS_MIN } from "./dimensions";

const mean = (a: number[]) => a.reduce((x, y) => x + y, 0) / a.length;

function normalise(v: number, sc: { min: number; max: number }, rev: boolean): number | null {
  if (!Number.isFinite(v) || v < sc.min || v > sc.max || sc.max === sc.min) return null;
  const pct = ((v - sc.min) / (sc.max - sc.min)) * 100;
  return rev ? 100 - pct : pct;
}

function band(mean_: number, n: number): Band["band"] {
  if (n === 0) return "none";
  if (n < MIN_N) return "thin";
  if (mean_ >= BAND_GOOD) return "good";
  if (mean_ >= BAND_WARN) return "warn";
  return "crit";
}

export const canon = (raw: string, alias: Record<string, string>): string => alias[raw] ?? raw;

/** Every raw group value across sources, before aliasing — what step 2's alignment table lists. */
export function segmentValues(sources: Source[]): Map<string, { rows: number; sources: Set<string>; whole: boolean }> {
  const out = new Map<string, { rows: number; sources: Set<string>; whole: boolean }>();
  for (const src of sources) {
    const segCol = src.map.findIndex((m) => m.role === "segment");
    if (segCol < 0) {
      const key = `(all of ${src.label})`;
      const e = out.get(key) ?? { rows: 0, sources: new Set<string>(), whole: true };
      e.rows += src.table.body.length;
      e.sources.add(src.sid);
      out.set(key, e);
      continue;
    }
    for (const r of src.table.body) {
      const key = r[segCol] || "(unstated)";
      const e = out.get(key) ?? { rows: 0, sources: new Set<string>(), whole: false };
      e.rows++;
      e.sources.add(src.sid);
      out.set(key, e);
    }
  }
  return out;
}

/** Case/spacing/punctuation variants merge automatically — the same name in different clothes. */
export function autoAlias(sources: Source[]): Record<string, string> {
  const alias: Record<string, string> = {};
  const seen = new Map<string, string>();
  for (const raw of segmentValues(sources).keys()) {
    if (raw.startsWith("(all of ")) continue;
    const k = raw.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    if (seen.has(k)) {
      const keep = seen.get(k)!;
      if (raw !== keep) alias[raw] = keep;
    } else seen.set(k, raw);
  }
  return alias;
}

/**
 * A likely-but-not-certain match: same first word, or one name a prefix of
 * the other. Suggested, never applied — "Field Ops" and "Field Operations"
 * are usually the same team and occasionally are not, and only the person
 * holding the data knows which.
 */
export function suggestMatch(raw: string, canonical: string[], alias: Record<string, string>): string | null {
  if (raw.startsWith("(all of ")) return null;
  const norm = (v: string) => v.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  const a = norm(raw);
  const first = a.split(" ")[0];
  if (a.length < 3) return null;
  for (const c of canonical) {
    if (c === raw || canon(raw, alias) === c || c.startsWith("(all of ")) continue;
    const b = norm(c);
    if (b === a) continue;
    const sameFirst = first.length >= 4 && b.split(" ")[0] === first;
    const prefix = (a.length >= 4 && b.startsWith(a)) || (b.length >= 4 && a.startsWith(b));
    if (sameFirst || prefix) return c;
  }
  return null;
}

export function analyse(sources: Source[], alias: Record<string, string>): Analysis {
  const rows: { sid: string; seg: string; dim: DimKey; v: number }[] = [];
  const comments: Comment[] = [];
  let dropped = 0;

  for (const src of sources) {
    const segCol = src.map.findIndex((m) => m.role === "segment");
    const scoreCols = src.map.map((m, i) => ({ ...m, i })).filter((m) => m.role === "score");
    const commentCols = src.map.map((m, i) => ({ ...m, i })).filter((m) => m.role === "comment");
    const wholeKey = `(all of ${src.label})`;

    src.table.body.forEach((r, ri) => {
      const seg = canon(segCol >= 0 ? r[segCol] || "(unstated)" : wholeKey, alias);
      for (const c of scoreCols) {
        const raw = r[c.i];
        if (raw === "") {
          dropped++;
          continue;
        }
        const n = normalise(Number(raw), c.scale, c.reverse);
        if (n === null) {
          dropped++;
          continue;
        }
        rows.push({ sid: src.sid, seg, dim: c.dimension, v: n });
      }
      for (const c of commentCols) {
        const t = (r[c.i] || "").trim();
        if (t.length >= 3) {
          comments.push({
            id: `${src.sid}-R${ri + 1}`,
            sid: src.sid,
            source: src.label,
            seg,
            dim: c.dimension,
            col: c.name,
            text: t,
          });
        }
      }
    });
  }

  const segments = [...new Set(rows.map((r) => r.seg).concat(comments.map((c) => c.seg)))].sort();
  const dims = [...new Set(rows.map((r) => r.dim))].sort(
    (a, b) => DIM_ORDER.indexOf(a) - DIM_ORDER.indexOf(b),
  );

  const pick = (d: DimKey, sg: string) => rows.filter((r) => r.dim === d && r.seg === sg);

  const matrix = dims.map((d) => ({
    dim: d,
    cells: segments.map((sg): Cell => {
      const hits = pick(d, sg);
      const v = hits.map((h) => h.v);
      const n = v.length;
      const bySource: Record<string, { n: number; mean: number }> = {};
      for (const sid of new Set(hits.map((h) => h.sid))) {
        const sv = hits.filter((h) => h.sid === sid).map((h) => h.v);
        bySource[sid] = { n: sv.length, mean: mean(sv) };
      }
      const m = n ? mean(v) : null;
      return {
        dim: d,
        seg: sg,
        n,
        mean: m,
        band: band(m ?? 0, n),
        neg: n ? (v.filter((x) => x <= NEG_MAX).length / n) * 100 : 0,
        pos: n ? (v.filter((x) => x >= POS_MIN).length / n) * 100 : 0,
        bySource,
      };
    }),
  }));

  const dimTotals = dims.map((d) => {
    const v = rows.filter((r) => r.dim === d).map((r) => r.v);
    const n = v.length;
    return {
      dim: d,
      n,
      mean: n ? mean(v) : null,
      neg: n ? (v.filter((x) => x <= NEG_MAX).length / n) * 100 : 0,
      pos: n ? (v.filter((x) => x >= POS_MIN).length / n) * 100 : 0,
      mid: n ? (v.filter((x) => x > NEG_MAX && x < POS_MIN).length / n) * 100 : 0,
    };
  });

  const blind: Cell[] = [];
  for (const row of matrix) for (const c of row.cells) if (c.band === "none" || c.band === "thin") blind.push(c);

  const respondents = sources.reduce((a, s) => a + s.table.body.length, 0);
  return {
    segments,
    dims,
    matrix,
    dimTotals,
    comments,
    blind,
    dropped,
    respondents,
    sources: sources.map((s) => ({
      sid: s.sid,
      label: s.label,
      file: s.file,
      sheet: s.sheetName,
      rows: s.table.body.length,
    })),
  };
}

/** Rule-based observations — arithmetic, not judgement. */
export function findings(a: Analysis): Finding[] {
  const out: Finding[] = [];
  const all = a.matrix.flatMap((r) => r.cells).filter((c) => c.n >= MIN_N);
  const label = (sid: string) => a.sources.find((s) => s.sid === sid)?.label ?? sid;

  const worst = [...all].sort((x, y) => (x.mean ?? 0) - (y.mean ?? 0))[0];
  if (worst && worst.mean !== null && worst.mean < BAND_WARN) {
    out.push({
      kind: "crit",
      tag: "Lowest",
      title: `${DIMLABEL[worst.dim]} in ${worst.seg} is the weakest reading at ${worst.mean.toFixed(0)}/100`,
      body: `${worst.neg.toFixed(0)}% of those responses were negative. Before treating it as the priority, check whether it is the finding or just the lowest number — what it predicts matters more than where it ranks.`,
      ev: `${DIMLABEL[worst.dim]} × ${worst.seg} · n=${worst.n}`,
    });
  }

  // Two instruments, one question, different answers — only visible once files are read together.
  for (const row of a.matrix) {
    for (const c of row.cells) {
      const per = Object.entries(c.bySource).filter(([, v]) => v.n >= MIN_N);
      if (per.length < 2) continue;
      const hi = per.reduce((p, x) => (x[1].mean > p[1].mean ? x : p));
      const lo = per.reduce((p, x) => (x[1].mean < p[1].mean ? x : p));
      if (hi[1].mean - lo[1].mean >= 15) {
        out.push({
          kind: "warn",
          tag: "Sources differ",
          title: `${label(lo[0])} and ${label(hi[0])} disagree about ${DIMLABEL[c.dim]} in ${c.seg}`,
          body: `${lo[1].mean.toFixed(0)} against ${hi[1].mean.toFixed(0)} on the same dimension for the same group. Check what actually separates them — different questions, a different moment, or a different set of people answering — before pooling them into one number.`,
          ev: `${label(lo[0])} n=${lo[1].n} · ${label(hi[0])} n=${hi[1].n}`,
        });
      }
    }
  }

  for (const row of a.matrix) {
    const seen = row.cells.filter((c) => c.n >= MIN_N);
    if (seen.length < 2) continue;
    const hi = seen.reduce((p, c) => ((c.mean ?? 0) > (p.mean ?? 0) ? c : p));
    const lo = seen.reduce((p, c) => ((c.mean ?? 0) < (p.mean ?? 0) ? c : p));
    const gap = (hi.mean ?? 0) - (lo.mean ?? 0);
    if (gap >= 20) {
      out.push({
        kind: "warn",
        tag: "Spread",
        title: `${DIMLABEL[row.dim]} splits the population: ${lo.seg} at ${(lo.mean ?? 0).toFixed(0)}, ${hi.seg} at ${(hi.mean ?? 0).toFixed(0)}`,
        body: `A ${gap.toFixed(0)}-point gap on the same question. An average across these two groups describes nobody, and one intervention will not serve both.`,
        ev: `${DIMLABEL[row.dim]} × ${lo.seg} (n=${lo.n}) vs ${hi.seg} (n=${hi.n})`,
      });
    }
  }

  const sk = a.dimTotals.find((d) => d.dim === "skills");
  const cf = a.dimTotals.find((d) => d.dim === "confidence");
  if (sk && cf && sk.n >= MIN_N && cf.n >= MIN_N && (sk.mean ?? 0) - (cf.mean ?? 0) >= 12) {
    out.push({
      kind: "info",
      tag: "Pattern",
      title: `Skills read ${((sk.mean ?? 0) - (cf.mean ?? 0)).toFixed(0)} points higher than confidence`,
      body: `People say they can do the task but not that they will cope on day one. Comprehension is not the constraint here — look at system readiness, capacity, and who will be there on the first morning.`,
      ev: `Skills ${(sk.mean ?? 0).toFixed(0)} (n=${sk.n}) vs Confidence ${(cf.mean ?? 0).toFixed(0)} (n=${cf.n})`,
    });
  }

  const aw = a.dimTotals.find((d) => d.dim === "awareness");
  const un = a.dimTotals.find((d) => d.dim === "understanding");
  if (aw && un && aw.n >= MIN_N && un.n >= MIN_N && (aw.mean ?? 0) - (un.mean ?? 0) >= 12) {
    out.push({
      kind: "info",
      tag: "Pattern",
      title: `People are reached but not told what changes for them — awareness ${(aw.mean ?? 0).toFixed(0)}, understanding ${(un.mean ?? 0).toFixed(0)}`,
      body: `The channel is working and the content is not. This is a comms-design finding, not a comms-volume one: more of the same bulletin will move the first number and not the second.`,
      ev: `Awareness ${(aw.mean ?? 0).toFixed(0)} (n=${aw.n}) vs Understanding ${(un.mean ?? 0).toFixed(0)} (n=${un.n})`,
    });
  }

  for (const d of a.dimTotals) {
    if (d.n >= MIN_N && d.neg >= 30 && d.pos >= 30) {
      out.push({
        kind: "warn",
        tag: "Divided",
        title: `${DIMLABEL[d.dim]} is a divided room, not a lukewarm one`,
        body: `${d.neg.toFixed(0)}% negative and ${d.pos.toFixed(0)}% positive on the same question. The mean of ${(d.mean ?? 0).toFixed(0)} describes almost nobody who answered it — find out what separates the two halves before acting on the average.`,
        ev: `${DIMLABEL[d.dim]} · n=${d.n}`,
      });
    }
  }

  const noData = a.blind.filter((c) => c.band === "none");
  const thin = a.blind.filter((c) => c.band === "thin");
  if (noData.length) {
    const segs = [...new Set(noData.map((c) => c.seg))];
    out.push({
      kind: "crit",
      tag: "Missing",
      title: `${noData.length} combination${noData.length > 1 ? "s" : ""} returned nothing at all`,
      body: `Affects ${segs.slice(0, 4).join(", ")}${segs.length > 4 ? ` and ${segs.length - 4} more` : ""}. An empty cell is not a green one. Before this snapshot goes to anyone, say plainly which groups it does not describe — including any group that was never sent the survey and so cannot appear here at all.`,
      ev: noData.slice(0, 6).map((c) => `${DIMLABEL[c.dim]} × ${c.seg}`).join(" · "),
    });
  }
  if (thin.length) {
    out.push({
      kind: "warn",
      tag: "Thin",
      title: `${thin.length} cell${thin.length > 1 ? "s" : ""} rest on fewer than ${MIN_N} responses`,
      body: `Held back from the colour banding rather than shown as on track. Four enthusiastic replies out of a hundred people is not a green cell — treat these as questions to chase, not as readings.`,
      ev: thin.slice(0, 6).map((c) => `${DIMLABEL[c.dim]} × ${c.seg} (n=${c.n})`).join(" · "),
    });
  }

  const best = [...all].sort((x, y) => (y.mean ?? 0) - (x.mean ?? 0))[0];
  if (best && best.mean !== null && best.mean >= BAND_GOOD) {
    out.push({
      kind: "good",
      tag: "Working",
      title: `${DIMLABEL[best.dim]} in ${best.seg} is the strongest reading at ${best.mean.toFixed(0)}/100`,
      body: `Worth naming out loud, and worth protecting when time gets short — whatever produced this is the thing most likely to be cut first.`,
      ev: `${DIMLABEL[best.dim]} × ${best.seg} · n=${best.n}`,
    });
  }

  const order: Record<Finding["kind"], number> = { crit: 0, warn: 1, info: 2, good: 3 };
  return out.sort((x, y) => order[x.kind] - order[y.kind]);
}
