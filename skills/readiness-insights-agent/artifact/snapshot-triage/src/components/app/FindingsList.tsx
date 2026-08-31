import type { Finding, FindingKind } from "@/lib/types";

const BORDER: Record<FindingKind, string> = {
  crit: "border-l-clay",
  warn: "border-l-amber",
  good: "border-l-jade",
  info: "border-l-brand",
};

export function FindingsList({ findings }: { findings: Finding[] }) {
  if (!findings.length) {
    return (
      <p className="max-w-[74ch] text-sm text-ink-2">
        Nothing crossed a threshold worth flagging — no cell below 55, no gap over 20 points, no empty
        cells, no source disagreeing with another. Read the heatmap and the comments directly.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {findings.map((f, i) => (
        <div
          key={i}
          className={`grid grid-cols-[auto_1fr] gap-3 rounded-[10px] border border-line border-l-4 bg-surface px-5 py-3.5 shadow-soft ${BORDER[f.kind]}`}
        >
          <div className="pt-0.5 font-data text-[10px] uppercase tracking-wider text-ink-3">{f.tag}</div>
          <div>
            <h3 className="mb-1 font-display text-[17px] font-semibold text-ink">{f.title}</h3>
            <p className="text-sm text-ink-2">{f.body}</p>
            <p className="mt-1.5 font-data text-[11.5px] text-ink-3">{f.ev}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
