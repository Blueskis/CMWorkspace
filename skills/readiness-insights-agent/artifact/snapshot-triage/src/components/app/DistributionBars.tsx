import type { Analysis, DimTotal } from "@/lib/types";
import { DIMLABEL } from "@/lib/dimensions";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function Row({ d }: { d: DimTotal }) {
  return (
    <div className="grid grid-cols-[150px_1fr_116px] items-center gap-3.5 py-1.5 sm:grid-cols-[150px_1fr_116px] max-sm:grid-cols-1 max-sm:gap-1">
      <div className="text-sm font-semibold text-ink">{DIMLABEL[d.dim]}</div>
      <Tooltip delayDuration={150}>
        <TooltipTrigger asChild>
          <div className="flex h-4 gap-0.5 overflow-hidden rounded-[2px] bg-line">
            {d.n > 0 && (
              <>
                {d.neg > 0 && <i className="block h-full bg-clay" style={{ width: `${d.neg}%` }} />}
                {d.mid > 0 && <i className="block h-full bg-line-strong" style={{ width: `${d.mid}%` }} />}
                {d.pos > 0 && <i className="block h-full bg-brand" style={{ width: `${d.pos}%` }} />}
              </>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent className="border-line bg-ink text-paper">
          <div className="max-w-[280px] text-[12.5px] leading-relaxed">
            <b className="font-display">{DIMLABEL[d.dim]}</b>
            <span className="mt-0.5 block font-data text-[11px] opacity-80">n={d.n}</span>
            {d.n ? (
              <>
                <span>
                  {d.neg.toFixed(0)}% negative · {d.mid.toFixed(0)}% neutral · {d.pos.toFixed(0)}% positive
                </span>
                <br />
                <span>Mean {(d.mean ?? 0).toFixed(1)}/100</span>
              </>
            ) : (
              <span>No responses.</span>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
      <div className="font-data text-xs tabular text-ink-2 sm:text-right">
        {d.n ? `${(d.mean ?? 0).toFixed(0)} · n=${d.n}` : "no data"}
      </div>
    </div>
  );
}

export function DistributionBars({ a }: { a: Analysis }) {
  return (
    <div className="flex flex-col gap-1">
      {a.dimTotals.map((d) => (
        <Row key={d.dim} d={d} />
      ))}
      <div className="mt-2 flex flex-wrap items-center gap-4 text-[12.5px] text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-[2px] bg-clay" /> Negative (≤ 40)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-[2px] bg-line-strong" /> Neutral (41–69)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-[2px] bg-brand" /> Positive (≥ 70)
        </span>
      </div>
    </div>
  );
}
