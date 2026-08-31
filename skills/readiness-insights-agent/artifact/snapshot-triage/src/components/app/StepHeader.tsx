interface StepHeaderProps {
  n: number;
  title: string;
  hint: string;
}

/** The numbering here is a real sequence — load, map, read — not decoration. */
export function StepHeader({ n, title, hint }: StepHeaderProps) {
  return (
    <div className="mb-4 flex items-baseline gap-3">
      <span className="flex-none rounded-full border border-brand px-2.5 py-0.5 font-data text-xs font-semibold text-brand">
        {n}
      </span>
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
        <p className="text-sm text-ink-2">{hint}</p>
      </div>
    </div>
  );
}
