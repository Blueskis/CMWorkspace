import { useMemo, useState } from "react";
import type { Analysis } from "@/lib/types";
import { DIMLABEL, STOPWORDS } from "@/lib/dimensions";

const selectCls =
  "rounded-[6px] border border-line-strong bg-surface px-2 py-1 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";

function tokens(text: string): string[] {
  return (text.toLowerCase().match(/[a-z][a-z'-]{2,}/g) ?? []).filter((w) => !STOPWORDS.has(w));
}

export function CommentsExplorer({ a }: { a: Analysis }) {
  const [group, setGroup] = useState("");
  const [dim, setDim] = useState("");
  const [source, setSource] = useState("");

  const segs = useMemo(() => [...new Set(a.comments.map((c) => c.seg))].sort(), [a.comments]);
  const dims = useMemo(() => [...new Set(a.comments.map((c) => c.dim))], [a.comments]);
  const srcs = useMemo(() => [...new Set(a.comments.map((c) => c.sid))], [a.comments]);

  const list = useMemo(
    () => a.comments.filter((c) => (!group || c.seg === group) && (!dim || c.dim === dim) && (!source || c.sid === source)),
    [a.comments, group, dim, source],
  );

  const terms = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of list) for (const w of tokens(c.text)) counts.set(w, (counts.get(w) ?? 0) + 1);
    return [...counts.entries()].filter(([, n]) => n > 1).sort((x, y) => y[1] - x[1]).slice(0, 14);
  }, [list]);

  if (!a.comments.length) return null;

  return (
    <div className="flex flex-col gap-4 rounded-[10px] border border-line bg-surface p-[22px] shadow-soft">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold tracking-tight text-ink">What people wrote</h2>
        <p className="text-sm text-ink-2">
          Grouped so you can code them yourself. The word counts are a hint about where to look — they
          are not themes. &ldquo;Training&rdquo; appearing forty times means nothing; eleven people
          describing the same unusable exercise means a great deal.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        {srcs.length > 1 && (
          <label className="flex items-center gap-2 text-sm text-ink-2">
            Source
            <select className={selectCls} value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All sources</option>
              {srcs.map((sid) => (
                <option key={sid} value={sid}>
                  {a.sources.find((s) => s.sid === sid)?.label ?? sid}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 text-sm text-ink-2">
          Group
          <select className={selectCls} value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="">All groups</option>
            {segs.map((sg) => (
              <option key={sg} value={sg}>
                {sg}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          Dimension
          <select className={selectCls} value={dim} onChange={(e) => setDim(e.target.value)}>
            <option value="">All dimensions</option>
            {dims.map((d) => (
              <option key={d} value={d}>
                {DIMLABEL[d]}
              </option>
            ))}
          </select>
        </label>
        <span className="text-sm text-ink-2">
          {list.length} of {a.comments.length} comments
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {terms.length ? (
          terms.map(([w, n]) => (
            <span key={w} className="rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-[12.5px] text-ink-2">
              {w} <span className="font-data text-[11px] text-ink-3">{n}</span>
            </span>
          ))
        ) : (
          <span className="text-sm text-ink-3">No word repeats across this selection.</span>
        )}
      </div>

      <div className="flex max-h-[460px] flex-col gap-3 overflow-y-auto pr-1.5">
        {list.slice(0, 300).map((c) => (
          <div key={c.id} className="border-l-2 border-line-strong py-0.5 pl-3.5 text-[14.5px] italic text-ink-2">
            {c.text}
            <span className="mt-0.5 block font-data text-[11px] not-italic text-ink-3">
              {c.id} · {c.source} · {c.seg} · {DIMLABEL[c.dim]} · {c.col}
            </span>
          </div>
        ))}
        {list.length > 300 && <p className="text-sm text-ink-2">Showing the first 300. Narrow the filters to see the rest.</p>}
      </div>
    </div>
  );
}
