import type { DimKey } from "./types";

/**
 * Eight readiness dimensions, fixed. A training-evaluation item and a
 * comms-form item land in the same cell only because both were mapped to one
 * of these — the closed set is what makes cross-source comparison meaningful.
 */
export const DIMS: [DimKey, string, string[]][] = [
  ["awareness", "Awareness", ["inform", "aware", "hear", "communicat", "updat", "newsletter", "bulletin", "channel", "message"]],
  ["understanding", "Understanding", ["understand", "know what", "clear", "relevan", "process", "what changes", "impact on my", "content"]],
  ["buy_in", "Buy-in", ["support the", "believe", "worth", "benefit", "positive about", "committed", "motivat", "see the point"]],
  ["skills", "Skills", ["apply", "skill", "able to", "train", "practi", "exercise", "competen", "learn", "hands on", "hands-on"]],
  ["system_readiness", "System readiness", ["system", "tool", "platform", "data", "access", "environment", "technically", "works"]],
  ["capacity", "Capacity", ["time", "capacity", "workload", "busy", "bandwidth", "resourc", "absorb", "cover", "headroom"]],
  ["leadership_support", "Leadership support", ["manager", "leader", "sponsor", "supervisor", "my boss", "visible", "senior"]],
  ["confidence", "Confidence", ["confiden", "ready", "prepared", "go-live", "go live", "day one", "cope", "comfortab"]],
];

export const DIMLABEL: Record<DimKey, string> = Object.fromEntries(
  DIMS.map(([k, l]) => [k, l]),
) as Record<DimKey, string>;

export const DIM_ORDER: DimKey[] = DIMS.map(([k]) => k);

export const REVERSE_HINTS = [
  "extra workload", "how much extra", "difficult", "hard to", "concern",
  "worried", "risk of", "burden", "confus",
];

export const MIN_N = 5;
export const BAND_GOOD = 70;
export const BAND_WARN = 55;
export const NEG_MAX = 40;
export const POS_MIN = 70;

export const STOPWORDS = new Set(
  ("a an and are as at be been but by can could do does for from get got had " +
    "has have how i if in is it its just like me more much my no not of on or " +
    "our so than that the their them then there they this to too us was we " +
    "were what when which who will with would you your really very lot bit " +
    "thing things there's i'm we're don't didn't it's").split(" "),
);
