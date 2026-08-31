import { cn } from "@/lib/utils";

export type PillKind = "good" | "warn" | "crit" | "thin" | "none";

const STYLE: Record<PillKind, string> = {
  good: "bg-jade-soft text-jade",
  warn: "bg-amber-soft text-amber",
  crit: "bg-clay-soft text-clay",
  thin: "bg-surface-2 text-ink-2",
  none: "bg-surface-2 text-ink-3",
};

export const PILL_LABEL: Record<PillKind, string> = {
  good: "On track",
  warn: "Watch",
  crit: "At risk",
  thin: "Thin base",
  none: "No data",
};

export function StatusPill({ kind, children }: { kind: PillKind; children?: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 font-data text-[11px] font-semibold uppercase tracking-wide",
        STYLE[kind],
      )}
    >
      {children ?? PILL_LABEL[kind]}
    </span>
  );
}
