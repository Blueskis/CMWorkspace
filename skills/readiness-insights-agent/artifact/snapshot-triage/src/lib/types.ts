export type DimKey =
  | "awareness"
  | "understanding"
  | "buy_in"
  | "skills"
  | "system_readiness"
  | "capacity"
  | "leadership_support"
  | "confidence";

export type Role = "ignore" | "segment" | "score" | "comment";

export interface Scale {
  min: number;
  max: number;
}

export interface ColumnMap {
  name: string;
  role: Role;
  dimension: DimKey;
  scale: Scale;
  reverse: boolean;
  unmatched: boolean;
}

export interface ColumnProfile {
  index: number;
  name: string;
  values: string[];
  nums: number[];
  numeric: boolean;
  distinct: number;
  distinctValues: string[];
  avgLen: number;
  min: number | null;
  max: number | null;
  sample: string;
}

export interface Table {
  header: string[];
  body: string[][];
}

export interface SheetRef {
  name: string;
  index: number;
}

export interface Source {
  sid: string;
  file: string;
  label: string;
  sheets: SheetRef[] | null;
  sheetIndex: number;
  sheetName: string | null;
  table: Table;
  profiles: ColumnProfile[];
  map: ColumnMap[];
  /** Present for .xlsx sources so a sheet switch can re-read without re-uploading. */
  workbook?: import("./spreadsheet").Workbook;
}

export interface Band {
  band: "good" | "warn" | "crit" | "thin" | "none";
  n: number;
  mean: number | null;
}

export interface BySourceStat {
  n: number;
  mean: number;
}

export interface Cell extends Band {
  dim: DimKey;
  seg: string;
  neg: number;
  pos: number;
  bySource: Record<string, BySourceStat>;
}

export interface DimTotal {
  dim: DimKey;
  n: number;
  mean: number | null;
  neg: number;
  pos: number;
  mid: number;
}

export interface Comment {
  id: string;
  sid: string;
  source: string;
  seg: string;
  dim: DimKey;
  col: string;
  text: string;
}

export interface SourceSummary {
  sid: string;
  label: string;
  file: string;
  sheet: string | null;
  rows: number;
}

export interface Analysis {
  segments: string[];
  dims: DimKey[];
  matrix: { dim: DimKey; cells: Cell[] }[];
  dimTotals: DimTotal[];
  comments: Comment[];
  blind: Cell[];
  dropped: number;
  respondents: number;
  sources: SourceSummary[];
}

export type FindingKind = "crit" | "warn" | "info" | "good";

export interface Finding {
  kind: FindingKind;
  tag: string;
  title: string;
  body: string;
  ev: string;
}
