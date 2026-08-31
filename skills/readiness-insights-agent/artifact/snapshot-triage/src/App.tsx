import { useCallback, useMemo, useRef, useState } from "react";
import type { Analysis, ColumnMap, Source } from "@/lib/types";
import { parseDelimited, readWorkbook, toTable } from "@/lib/spreadsheet";
import { guessRoles, profile } from "@/lib/profiling";
import { analyse, autoAlias, findings, segmentValues, canon } from "@/lib/analysis";
import { summaryCsv, fullJson } from "@/lib/exportData";
import { offerDownload } from "@/lib/downloads";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { StepHeader } from "@/components/app/StepHeader";
import { FileDrop } from "@/components/app/FileDrop";
import { SourceTable } from "@/components/app/SourceTable";
import { MappingBlock } from "@/components/app/MappingBlock";
import { AlignmentPanel } from "@/components/app/AlignmentPanel";
import { KpiRow } from "@/components/app/KpiRow";
import { Heatmap } from "@/components/app/Heatmap";
import { DistributionBars } from "@/components/app/DistributionBars";
import { FindingsList } from "@/components/app/FindingsList";
import { CommentsExplorer } from "@/components/app/CommentsExplorer";

function niceLabel(name: string, sheet: string | null) {
  const base = name.replace(/\.[a-z]+$/i, "").replace(/[_-]+/g, " ").trim() || "Source";
  return sheet ? `${base} — ${sheet}` : base;
}

let seq = 0;
const nextSid = () => "S" + ++seq;

export default function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [alias, setAlias] = useState<Record<string, string>>({});
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dlNote, setDlNote] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const readSectionRef = useRef<HTMLDivElement>(null);
  const mapSectionRef = useRef<HTMLDivElement>(null);

  const rebuildAlias = useCallback((next: Source[]) => setAlias(autoAlias(next)), []);

  const buildSource = (file: string, sheets: Source["sheets"], sheetIdx: number, rows: string[][], workbook?: Source["workbook"]): Source => {
    const table = toTable(rows);
    const profiles = profile(table);
    const sheetName = sheets ? sheets[sheetIdx].name : null;
    return {
      sid: nextSid(),
      file,
      sheets,
      sheetIndex: sheetIdx,
      sheetName,
      table,
      profiles,
      label: niceLabel(file, sheets && sheets.length > 1 ? sheetName : null),
      map: guessRoles(profiles, table.body.length).map((m, i) => ({ ...m, name: profiles[i].name })),
      workbook,
    };
  };

  const readOne = async (f: File): Promise<Source> => {
    if (/\.(csv|tsv|txt)$/i.test(f.name)) {
      return buildSource(f.name, null, 0, parseDelimited(await f.text()));
    }
    const wb = await readWorkbook(await f.arrayBuffer());
    return buildSource(f.name, wb.sheets, 0, wb.readSheet(0), wb);
  };

  const handleFiles = async (files: File[]) => {
    setLoadError(null);
    const problems: string[] = [];
    const added: Source[] = [];
    for (const f of files) {
      try {
        added.push(await readOne(f));
      } catch (err) {
        problems.push(`${f.name}: ${(err as Error).message}`);
      }
    }
    if (problems.length) setLoadError(problems.join("  ") + (added.length ? " Everything else was loaded." : ""));
    if (!added.length && !sources.length) return;
    const next = [...sources, ...added];
    setSources(next);
    setAnalysis(null);
    rebuildAlias(next);
    requestAnimationFrame(() => mapSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  const handleSheetChange = (sid: string, index: number) => {
    setSources((prev) => {
      const src = prev.find((s) => s.sid === sid);
      if (!src || !src.sheets || !src.workbook) return prev;
      try {
        const rows = src.workbook.readSheet(index);
        const table = toTable(rows);
        const profiles = profile(table);
        const sheetName = src.sheets[index].name;
        const rebuilt: Source = {
          ...src,
          sheetIndex: index,
          sheetName,
          table,
          profiles,
          map: guessRoles(profiles, table.body.length).map((m, i) => ({ ...m, name: profiles[i].name })),
          label: niceLabel(src.file, src.sheets.length > 1 ? sheetName : null),
        };
        const next = prev.map((s) => (s.sid === sid ? rebuilt : s));
        rebuildAlias(next);
        return next;
      } catch (err) {
        setLoadError(`Sheet "${src.sheets![index].name}" could not be read: ${(err as Error).message}`);
        return prev;
      }
    });
    setAnalysis(null);
  };

  const handleLabelChange = (sid: string, label: string) => {
    setSources((prev) => prev.map((s) => (s.sid === sid ? { ...s, label } : s)));
  };

  const handleRemove = (sid: string) => {
    setSources((prev) => {
      const next = prev.filter((s) => s.sid !== sid);
      if (!next.length) {
        setAlias({});
        setAnalysis(null);
        return next;
      }
      rebuildAlias(next);
      return next;
    });
    setAnalysis(null);
  };

  const handleMappingChange = (sid: string, colIndex: number, patch: Partial<ColumnMap>) => {
    setSources((prev) => {
      const next = prev.map((s) => {
        if (s.sid !== sid) return s;
        const map = s.map.map((m, i) => (i === colIndex ? { ...m, ...patch } : m));
        if (patch.role === "segment") {
          for (let j = 0; j < map.length; j++) if (j !== colIndex && map[j].role === "segment") map[j] = { ...map[j], role: "ignore" };
        }
        return { ...s, map };
      });
      if (patch.role === "segment" || patch.role === "ignore") rebuildAlias(next);
      return next;
    });
  };

  const handleAliasChange = (raw: string, target: string | null) => {
    setAlias((prev) => {
      const next = { ...prev };
      if (target) next[raw] = target;
      else delete next[raw];
      return next;
    });
  };

  const handleReset = () => {
    setSources([]);
    setAlias({});
    setAnalysis(null);
    setLoadError(null);
    seq = 0;
  };

  const handleRun = () => {
    const result = analyse(sources, alias);
    setAnalysis(result);
    requestAnimationFrame(() => readSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  const values = useMemo(() => segmentValues(sources), [sources]);
  const groupCount = useMemo(() => new Set([...values.keys()].map((v) => canon(v, alias))).size, [values, alias]);
  const scoreCount = sources.reduce((a, s) => a + s.map.filter((m) => m.role === "score").length, 0);

  const findingsList = analysis ? findings(analysis) : [];

  return (
    <TooltipProvider delayDuration={150}>
      <div className="mx-auto max-w-[1120px] px-[22px] pb-24 pt-9">
        <header className="mb-2 flex flex-col gap-3 border-b-2 border-ink pb-6">
          <div>
            <p className="mb-1.5 font-data text-[11px] font-medium uppercase tracking-[0.13em] text-ink-3">
              Change readiness · quick-look
            </p>
            <h1 className="font-display text-[clamp(28px,4.4vw,40px)] font-bold leading-[1.08] tracking-tight text-ink">
              Readiness Snapshot Triage
            </h1>
            <p className="mt-2 max-w-[66ch] text-[17px] text-ink-2">
              Drop in your feedback exports — training evaluations, a comms feedback form, a readiness
              assessment — and read them together: where each group actually stands, where two sources
              disagree, which cells are too thin to trust, and who is missing from the data entirely.
            </p>
          </div>
          <p className="max-w-[74ch] text-[13.5px] text-ink-3">
            <strong className="text-ink-2">Your files stay in this browser.</strong> Every spreadsheet is
            parsed on your own machine and nothing is uploaded, stored, or sent anywhere. Close the tab and
            it is gone.
          </p>
        </header>

        <section className="mt-8">
          <StepHeader n={1} title="Load the exports" hint="One or several files — .xlsx or .csv, one row per respondent, one header row each." />

          {sources.length === 0 ? (
            <FileDrop onFiles={handleFiles} />
          ) : (
            <SourceTable
              sources={sources}
              onSheetChange={handleSheetChange}
              onLabelChange={handleLabelChange}
              onRemove={handleRemove}
              onAddMore={() => fileInputRef.current?.click()}
              onReset={handleReset}
            />
          )}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".xlsx,.csv,.tsv,text/csv"
            className="hidden"
            onChange={(e) => {
              const files = [...(e.target.files ?? [])];
              e.target.value = "";
              if (files.length) handleFiles(files);
            }}
          />
          {loadError && (
            <div className="mt-3 rounded-[8px] border border-clay/40 border-l-4 border-l-clay bg-clay-soft px-4 py-3 text-sm text-ink-2">
              {loadError}
            </div>
          )}
        </section>

        {sources.length > 0 && (
          <section className="mt-8" ref={mapSectionRef}>
            <StepHeader n={2} title="Check the column mapping" hint="Guessed from the headers, per file. Correct anything wrong — the read below is only as good as this." />
            <div className="flex flex-col gap-4">
              {sources.map((src) => (
                <MappingBlock key={src.sid} source={src} onChange={handleMappingChange} />
              ))}
            </div>

            <AlignmentPanel sources={sources} alias={alias} onAliasChange={handleAliasChange} />

            <div className="mt-3.5 flex flex-wrap items-center gap-3">
              <Button
                type="button"
                disabled={scoreCount === 0}
                onClick={handleRun}
                className="bg-brand text-brand-ink hover:brightness-110 disabled:opacity-45"
              >
                Read the snapshot
              </Button>
              <span className="text-sm text-ink-2">
                {scoreCount === 0
                  ? "No score columns mapped yet — mark at least one column as a Score."
                  : `${scoreCount} score column${scoreCount === 1 ? "" : "s"} across ${sources.length} source${sources.length === 1 ? "" : "s"}, ${groupCount} group${groupCount === 1 ? "" : "s"} after merging.`}
              </span>
            </div>
          </section>
        )}

        {analysis && (
          <section className="mt-8" ref={readSectionRef}>
            <StepHeader
              n={3}
              title="The read"
              hint={`${analysis.sources.length} source${analysis.sources.length === 1 ? "" : "s"} · ${analysis.respondents} respondents · ${analysis.segments.length} group${analysis.segments.length === 1 ? "" : "s"} · ${analysis.dims.length} dimension${analysis.dims.length === 1 ? "" : "s"}${analysis.dropped ? ` · ${analysis.dropped} blank or out-of-scale answers left out rather than filled in` : ""}`}
            />

            <KpiRow a={analysis} />

            <div className="mt-5 flex flex-col gap-3.5 rounded-[10px] border border-line bg-surface p-[22px] shadow-soft">
              <div className="flex flex-col gap-1">
                <h2 className="text-xl font-semibold tracking-tight text-ink">Where each group stands</h2>
                <p className="text-sm text-ink-2">
                  Every score normalised to 0–100, higher is better. A base under 5 responses is marked
                  <em> thin</em> and never shown as on track, however high it scores.
                </p>
              </div>
              <Heatmap a={analysis} />
            </div>

            <div className="mt-5 flex flex-col gap-3.5 rounded-[10px] border border-line bg-surface p-[22px] shadow-soft">
              <div className="flex flex-col gap-1">
                <h2 className="text-xl font-semibold tracking-tight text-ink">How the answers split</h2>
                <p className="text-sm text-ink-2">
                  An average hides a divided room. Each bar is the share of responses that were negative,
                  neutral, or positive on that dimension — two groups pulling apart look nothing like a
                  room that is mildly lukewarm, and they need opposite responses.
                </p>
              </div>
              <DistributionBars a={analysis} />
            </div>

            <div className="mt-5 flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <h2 className="text-xl font-semibold tracking-tight text-ink">What stands out</h2>
                <p className="text-sm text-ink-2">
                  Computed from the numbers above, not judged. Each one names the cells behind it so you
                  can check it. Read these as prompts for the conversation, not as conclusions.
                </p>
              </div>
              <FindingsList findings={findingsList} />
            </div>

            <div className="mt-5">
              <CommentsExplorer a={analysis} />
            </div>

            <div className="mt-5 flex flex-col gap-3.5 rounded-[10px] border border-line bg-surface p-[22px] shadow-soft">
              <h2 className="text-xl font-semibold tracking-tight text-ink">Take it further</h2>
              <p className="text-sm text-ink-2">
                This page reads one snapshot on its own. To turn it into a briefed set of insights —
                themed comments, findings anchored to milestones with an action window, and an audit that
                fails when a blind spot goes undeclared — export the summary and hand it to the
                practitioner running the full readiness pipeline.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  className="bg-brand text-brand-ink hover:brightness-110"
                  onClick={async () => setDlNote(await offerDownload("readiness-summary.csv", summaryCsv(analysis)))}
                >
                  Download summary (.csv)
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={async () => setDlNote(await offerDownload("readiness-read.json", fullJson(analysis, alias)))}
                >
                  Download full read (.json)
                </Button>
                <span className="text-sm text-ink-2">{dlNote}</span>
              </div>
            </div>
          </section>
        )}

        <footer className="mt-14 flex flex-col gap-2 border-t border-line pt-[18px] text-[13px] text-ink-3">
          <p>
            <strong className="text-ink-2">A quick look, not an assessment.</strong> This page computes
            what the responses say. It cannot tell you whether the instrument asked the right question,
            whether the people who did not respond think something different, or what to do by when.
          </p>
          <p>
            Bands (70 / 55) and the thin-base floor (n = 5) are conventions, not findings. Say so when
            someone quotes a colour at you.
          </p>
        </footer>
      </div>
    </TooltipProvider>
  );
}
