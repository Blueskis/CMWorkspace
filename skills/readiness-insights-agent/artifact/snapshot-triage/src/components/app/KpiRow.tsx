import type { Analysis } from "@/lib/types";
import { BAND_WARN, MIN_N } from "@/lib/dimensions";

function Kpi({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-[10px] border border-line bg-surface px-4 py-3.5 shadow-soft">
      <div className="font-display text-[30px] font-bold leading-none tracking-tight text-ink">{value}</div>
      <div className="text-[12.5px] text-ink-2">{label}</div>
    </div>
  );
}

export function KpiRow({ a }: { a: Analysis }) {
  const scored = a.matrix.flatMap((r) => r.cells).filter((c) => c.n >= MIN_N);
  const overall = scored.length ? scored.reduce((s, c) => s + (c.mean ?? 0), 0) / scored.length : null;
  const risk = scored.filter((c) => c.band === "crit").length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Kpi value={String(a.sources.length)} label={`source${a.sources.length === 1 ? "" : "s"} read together`} />
      <Kpi value={String(a.respondents)} label="respondents" />
      <Kpi value={overall === null ? "—" : overall.toFixed(0)} label="mean across readable cells" />
      <Kpi value={String(risk)} label={`cell${risk === 1 ? "" : "s"} at risk (< ${BAND_WARN})`} />
      <Kpi value={String(a.blind.length)} label="cells thin or empty" />
      <Kpi value={String(a.comments.length)} label="written comments" />
    </div>
  );
}
