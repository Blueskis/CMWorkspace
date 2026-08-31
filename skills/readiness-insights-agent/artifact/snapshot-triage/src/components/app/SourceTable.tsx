import type { Source } from "@/lib/types";
import { Button } from "@/components/ui/button";

const selectCls =
  "rounded-[6px] border border-line-strong bg-surface px-2 py-1 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";
const inputCls =
  "w-full min-w-[180px] rounded-[6px] border border-line-strong bg-surface px-2 py-1 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";

interface SourceTableProps {
  sources: Source[];
  onSheetChange: (sid: string, index: number) => void;
  onLabelChange: (sid: string, label: string) => void;
  onRemove: (sid: string) => void;
  onAddMore: () => void;
  onReset: () => void;
}

export function SourceTable({ sources, onSheetChange, onLabelChange, onRemove, onAddMore, onReset }: SourceTableProps) {
  const totalRows = sources.reduce((a, s) => a + s.table.body.length, 0);

  return (
    <div className="rounded-[10px] border border-line bg-surface shadow-soft">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left font-data text-[10.5px] uppercase tracking-wider text-ink-3">
              <th className="px-4 py-2.5 font-medium">Source</th>
              <th className="px-4 py-2.5 font-medium">Sheet</th>
              <th className="px-4 py-2.5 font-medium">Rows</th>
              <th className="px-4 py-2.5 font-medium">Columns</th>
              <th className="px-4 py-2.5 font-medium">Label</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {sources.map((src) => (
              <tr key={src.sid} className="border-b border-line-soft last:border-0">
                <td className="px-4 py-2.5">
                  <span className="mr-2 font-data text-xs text-ink-3">{src.sid}</span>
                  <span className="font-medium text-ink">{src.file}</span>
                </td>
                <td className="px-4 py-2.5">
                  {src.sheets && src.sheets.length > 1 ? (
                    <select
                      className={selectCls}
                      value={src.sheetIndex}
                      onChange={(e) => onSheetChange(src.sid, Number(e.target.value))}
                    >
                      {src.sheets.map((sh) => (
                        <option key={sh.index} value={sh.index}>
                          {sh.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-ink-3">{src.sheetName ?? "—"}</span>
                  )}
                </td>
                <td className="px-4 py-2.5 tabular text-ink-2">{src.table.body.length}</td>
                <td className="px-4 py-2.5 tabular text-ink-2">{src.table.header.length}</td>
                <td className="px-4 py-2.5">
                  <input
                    type="text"
                    className={inputCls}
                    defaultValue={src.label}
                    onBlur={(e) => onLabelChange(src.sid, e.target.value.trim() || src.file)}
                  />
                </td>
                <td className="px-4 py-2.5">
                  <Button type="button" variant="ghost" size="sm" onClick={() => onRemove(src.sid)}>
                    Remove
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-3.5">
        <Button type="button" variant="outline" size="sm" onClick={onAddMore}>
          Add another file
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onReset}>
          Start over
        </Button>
        <span className="text-sm text-ink-2">
          {sources.length} file{sources.length === 1 ? "" : "s"}, {totalRows} rows in total. The label is
          what each source is called in the read — rename it to something you would say out loud.
        </span>
      </div>
    </div>
  );
}
