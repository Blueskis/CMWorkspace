import type { Source } from "@/lib/types";
import { canon, segmentValues, suggestMatch } from "@/lib/analysis";
import { Button } from "@/components/ui/button";

const selectCls =
  "rounded-[6px] border border-line-strong bg-surface px-2 py-1 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand max-w-[260px]";

interface AlignmentPanelProps {
  sources: Source[];
  alias: Record<string, string>;
  onAliasChange: (raw: string, target: string | null) => void;
}

/**
 * Group names are matched literally, so a spelling difference across exports
 * silently halves both bases. This is where that gets caught before it does.
 */
export function AlignmentPanel({ sources, alias, onAliasChange }: AlignmentPanelProps) {
  const values = segmentValues(sources);
  const canonical = [...new Set([...values.keys()].map((v) => canon(v, alias)))].sort();
  const worthShowing = sources.length > 1 || [...values.keys()].some((v) => canon(v, alias) !== v);
  if (!worthShowing || values.size === 0) return null;

  const rows = [...values.entries()].sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <div className="mt-4 flex flex-col gap-4 rounded-[10px] border border-line bg-surface p-[22px] shadow-soft">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold tracking-tight text-ink">Line up the group names</h2>
        <p className="text-sm text-ink-2">
          Group names are matched literally, so &ldquo;Field Ops&rdquo; in one export and &ldquo;Field
          Operations&rdquo; in another are two groups to the matrix — which quietly halves both bases.
          Point any spelling at the name you want to keep.
        </p>
      </div>
      <div className="overflow-x-auto rounded-[8px] border border-line-soft">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left font-data text-[10.5px] uppercase tracking-wider text-ink-3">
              <th className="px-4 py-2.5 font-medium">Value in the file</th>
              <th className="px-4 py-2.5 font-medium">Appears in</th>
              <th className="px-4 py-2.5 font-medium">Rows</th>
              <th className="px-4 py-2.5 font-medium">Read as</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([raw, info]) => {
              const current = alias[raw];
              const hit = !current ? suggestMatch(raw, canonical, alias) : null;
              return (
                <tr key={raw} className="border-t border-line-soft">
                  <td className="px-4 py-2.5 font-medium text-ink">{raw}</td>
                  <td className="px-4 py-2.5 text-ink-2">{[...info.sources].join(", ")}</td>
                  <td className="px-4 py-2.5 tabular text-ink-2">{info.rows}</td>
                  <td className="px-4 py-2.5">
                    <select
                      className={selectCls}
                      value={current ?? ""}
                      onChange={(e) => onAliasChange(raw, e.target.value || null)}
                    >
                      <option value="">Keep as &ldquo;{raw}&rdquo;</option>
                      {canonical
                        .filter((c) => c !== raw)
                        .map((c) => (
                          <option key={c} value={c}>
                            Merge into &ldquo;{c}&rdquo;
                          </option>
                        ))}
                    </select>
                    {current && <span className="ml-2 text-sm text-ink-2">→ counted as {current}</span>}
                    {!current && hit && (
                      <div className="mt-1.5 flex items-center gap-2 text-sm text-ink-2">
                        <span>
                          Looks like &ldquo;{hit}&rdquo;.
                        </span>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-6 px-2.5 text-xs"
                          onClick={() => onAliasChange(raw, hit)}
                        >
                          Merge them
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
