import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FileDropProps {
  onFiles: (files: File[]) => void;
}

export function FileDrop({ onFiles }: FileDropProps) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-[10px] border-[1.5px] border-dashed border-line-strong bg-surface px-6 py-10 text-center transition-colors",
        over && "border-brand bg-brand-soft",
      )}
      onDragEnter={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => {
        e.preventDefault();
        setOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const files = [...e.dataTransfer.files];
        if (files.length) onFiles(files);
      }}
    >
      <UploadCloud className="h-7 w-7 text-ink-3" strokeWidth={1.5} />
      <h3 className="font-display text-lg font-semibold text-ink">Drop your spreadsheets here</h3>
      <p className="max-w-md text-sm text-ink-2">
        Excel (.xlsx) or CSV, as many as you have. A training evaluation, a comms feedback form and a
        readiness assessment can be read together — each keeps its own column mapping and they pool
        into one matrix.
      </p>
      <Button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="bg-brand text-brand-ink hover:brightness-110"
      >
        Choose files
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".xlsx,.csv,.tsv,text/csv"
        className="hidden"
        onChange={(e) => {
          const files = [...(e.target.files ?? [])];
          e.target.value = "";
          if (files.length) onFiles(files);
        }}
      />
    </div>
  );
}
