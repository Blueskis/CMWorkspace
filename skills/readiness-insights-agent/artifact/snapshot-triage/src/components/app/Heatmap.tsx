import type { Analysis, Cell } from "@/lib/types";
import { DIMLABEL, MIN_N } from "@/lib/dimensions";
import { PILL_LABEL, type PillKind } from "./StatusPill";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const CELL_STYLE: Record<PillKind, string> = {
  good: "bg-jade-soft border-jade/30",
  warn: "bg-amber-soft border-amber/35",
  crit: "bg-clay-soft border-clay/30",
  thin: "bg-surface-2 border-line-soft",
  none: "bg-surface-2 border-line-soft",
};
const VALUE_STYLE: Record<PillKind, string> = {
  good: "text-jade",
  warn: "text-amber",
  crit: "text-clay",
  thin: "text-ink-2",
  none: "text-ink-3",
};

function label(a: Analysis, sid: string) {
  return a.sources.find((s) => s.sid === sid)?.label ?? sid;
}

function CellTip({ a, c }: { a: Analysis; c: Cell }) {
  const per = Object.entries(c.bySource);
  return (
    <div className="max-w-[280px] text-[12.5px] leading-relaxed">
      <b className="font-display">
        {DIMLABEL[c.dim]} · {c.seg}
      </b>
      <span className="mt-0.5 block font-data text-[11px] opacity-80">{PILL_LABEL[c.band]}</span>
      {c.n === 0 ? (
        <span>No responses in this combination.</span>
      ) : (
        <>
          <span>
            Mean {(c.mean ?? 0).toFixed(1)}/100 from {c.n} response{c.n === 1 ? "" : "s"}.
          </span>
          <br />
          <span>
            {c.neg.toFixed(0)}% negative · {c.pos.toFixed(0)}% positive
          </span>
          {per.length > 1 &&
            per.map(([sid, v]) => (
              <span key={sid} className="block">
                {label(a, sid)}: {v.mean.toFixed(0)} (n={v.n})
              </span>
            ))}
          {c.band === "thin" && <span className="block">Held back from banding — fewer than {MIN_N} responses.</span>}
        </>
      )}
    </div>
  );
}

export function Heatmap({ a }: { a: Analysis }) {
  return (
    <div className="flex flex-col gap-3.5">
      <div className="overflow-x-auto rounded-[8px] border border-line-soft">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left font-data text-[10.5px] uppercase tracking-wider text-ink-3">
              <th className="px-4 py-2.5 font-medium">Group</th>
              {a.dims.map((d) => (
                <th key={d} className="px-4 py-2.5 font-medium">
                  {DIMLABEL[d]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {a.segments.map((seg) => (
              <tr key={seg} className="border-t border-line-soft">
                <th className="whitespace-nowrap px-4 py-2.5 text-left font-display text-[13.5px] font-semibold text-ink">
                  {seg}
                </th>
                {a.dims.map((d) => {
                  const c = a.matrix.find((r) => r.dim === d)!.cells.find((x) => x.seg === seg)!;
                  return (
                    <td key={d} className="px-2 py-1.5">
                      <Tooltip delayDuration={150}>
                        <TooltipTrigger asChild>
                          <div
                            tabIndex={0}
                            className={`min-w-[104px] rounded-[3px] border px-2.5 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${CELL_STYLE[c.band]}`}
                          >
                            <span className={`font-display text-base font-bold tabular ${VALUE_STYLE[c.band]}`}>
                              {c.n === 0 ? "no data" : c.mean!.toFixed(0)}
                            </span>
                            <span className="mt-0.5 block font-data text-[10.5px] text-ink-3">
                              {c.n === 0 ? "not asked here" : `n=${c.n} · ${PILL_LABEL[c.band]}`}
                            </span>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent className="border-line bg-ink text-paper">
                          <CellTip a={a} c={c} />
                        </TooltipContent>
                      </Tooltip>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[12.5px] text-ink-2">
        <Legend kind="good" text="On track ≥ 70" />
        <Legend kind="warn" text="Watch 55–69" />
        <Legend kind="crit" text="At risk < 55" />
        <Legend kind="thin" text={`Thin base (n < ${MIN_N})`} />
        <Legend kind="none" text="No data" />
      </div>
    </div>
  );
}

function Legend({ kind, text }: { kind: PillKind; text: string }) {
  const dot: Record<PillKind, string> = {
    good: "bg-jade",
    warn: "bg-amber",
    crit: "bg-clay",
    thin: "bg-ink-3",
    none: "bg-line-strong",
  };
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2 w-2 rounded-[2px] ${dot[kind]}`} />
      {text}
    </span>
  );
}
