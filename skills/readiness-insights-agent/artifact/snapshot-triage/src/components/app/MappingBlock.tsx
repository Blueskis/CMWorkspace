import type { ColumnMap, Role, Source } from "@/lib/types";
import { DIMS } from "@/lib/dimensions";
import { SCALE_PRESETS } from "@/lib/profiling";

const selectCls =
  "rounded-[6px] border border-line-strong bg-surface px-2 py-1 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";

const ROLE_OPTIONS: [Role, string][] = [
  ["ignore", "Ignore"],
  ["segment", "Group / segment"],
  ["score", "Score"],
  ["comment", "Comment"],
];

interface MappingBlockProps {
  source: Source;
  onChange: (sid: string, colIndex: number, patch: Partial<ColumnMap>) => void;
}

/** One block per source — instruments do not share headers, so each keeps its own mapping. */
export function MappingBlock({ source, onChange }: MappingBlockProps) {
  const scores = source.map.filter((m) => m.role === "score").length;
  const comments = source.map.filter((m) => m.role === "comment").length;
  const seg = source.map.find((m) => m.role === "segment");

  return (
    <div className="rounded-[10px] border border-line bg-surface shadow-soft">
      <div className="flex flex-wrap items-baseline gap-2.5 border-b border-line bg-surface-2 px-[18px] py-3.5">
        <span className="rounded-full border border-brand px-2 py-0.5 font-data text-[11px] text-brand">{source.sid}</span>
        <h3 className="text-base font-semibold text-ink">{source.label}</h3>
        <span className="ml-auto text-sm text-ink-2">
          {scores} score · {comments} comment · {seg ? `grouped by "${seg.name}"` : "no grouping column"}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left font-data text-[10.5px] uppercase tracking-wider text-ink-3">
              <th className="px-4 py-2.5 font-medium">Column</th>
              <th className="px-4 py-2.5 font-medium">Read as</th>
              <th className="px-4 py-2.5 font-medium">Readiness dimension</th>
              <th className="px-4 py-2.5 font-medium">Scale</th>
              <th className="px-4 py-2.5 font-medium">Sample value</th>
            </tr>
          </thead>
          <tbody>
            {source.profiles.map((p, i) => {
              const m = source.map[i];
              return (
                <tr key={p.name + i} className="border-t border-line-soft">
                  <td className="max-w-[290px] px-4 py-2.5 font-medium text-ink">{p.name}</td>
                  <td className="px-4 py-2.5">
                    <select
                      className={selectCls}
                      value={m.role}
                      onChange={(e) => {
                        const role = e.target.value as Role;
                        const patch: Partial<ColumnMap> = { role };
                        if (role === "score" && !m.scale) patch.scale = { min: 1, max: 5 };
                        onChange(source.sid, i, patch);
                      }}
                    >
                      {ROLE_OPTIONS.map(([v, l]) => (
                        <option key={v} value={v}>
                          {l}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-2.5">
                    {m.role === "score" || m.role === "comment" ? (
                      <>
                        <select
                          className={selectCls}
                          value={m.dimension}
                          onChange={(e) => onChange(source.sid, i, { dimension: e.target.value as ColumnMap["dimension"], unmatched: false })}
                        >
                          {DIMS.map(([k, l]) => (
                            <option key={k} value={k}>
                              {l}
                            </option>
                          ))}
                        </select>
                        {m.unmatched && (
                          <span className="mt-1 block text-xs text-ink-3">guessed from nothing in the header — check it</span>
                        )}
                      </>
                    ) : (
                      <span className="text-ink-3">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {m.role === "score" ? (
                      <div className="flex items-center gap-2">
                        <select
                          className={selectCls}
                          value={`${m.scale.min}-${m.scale.max}`}
                          onChange={(e) => {
                            const found = SCALE_PRESETS.find(([label]) => label === e.target.value);
                            if (found) onChange(source.sid, i, { scale: found[1] });
                          }}
                        >
                          {SCALE_PRESETS.map(([label]) => (
                            <option key={label} value={label}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <label className="flex items-center gap-1.5 text-xs text-ink-2">
                          <input
                            type="checkbox"
                            checked={m.reverse}
                            onChange={(e) => onChange(source.sid, i, { reverse: e.target.checked })}
                          />
                          reverse
                        </label>
                      </div>
                    ) : (
                      <span className="text-ink-3">—</span>
                    )}
                  </td>
                  <td className="max-w-[280px] truncate px-4 py-2.5 text-ink-2">{p.sample || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
