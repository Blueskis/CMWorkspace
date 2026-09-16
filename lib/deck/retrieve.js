/**
 * BM25 retrieval — the JS twin of lib/deck_index.py, kept in exact parity (see
 * webapp/test/*-parity.mjs for the pattern; a shared-fixture parity test for this pair
 * lives at webapp/test/retrieve-parity.mjs). Same K1/B, same inverted-index shape, same
 * query-expansion/section-boost/RRF additions. Runs in the artifact (no Python available
 * in the browser) against a chunk_index.json built by build-index() below or handed over
 * from lib/deck_index.py's `index` command — either producer's output is readable by
 * either language's reader, by construction.
 *
 * No embeddings here either, same reasoning as the Python side: a ranking a practitioner
 * can't reason about can't be debugged when it pulls the wrong clause.
 */

const CHUNK_WORDS = 200;
const K1 = 1.5;
const B = 0.75;
const SECTION_PATH_BOOST = 1.5;
const WORD_RE = /[a-z0-9]+/gi;
const STOPWORDS = new Set([
  "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be",
  "this", "that", "with", "as", "by", "it", "at", "from", "will", "shall", "must",
  "if", "then", "not", "can", "may", "into", "their", "its", "each", "such",
]);

export function tokenize(text) {
  const matches = String(text).match(WORD_RE) ?? [];
  return matches.map((w) => w.toLowerCase()).filter((w) => !STOPWORDS.has(w));
}

export function chunkSection(section, origin = "prose") {
  const words = (section.text ?? "").split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const chunks = [];
  for (let i = 0; i < words.length; i += CHUNK_WORDS) {
    const text = words.slice(i, i + CHUNK_WORDS).join(" ");
    chunks.push({
      chunk_id: `${section.section_id}::c${Math.floor(i / CHUNK_WORDS) + 1}`,
      section_id: section.section_id,
      document_id: section.document_id,
      section_path: section.section_path,
      classifier: section.classifier ?? "narrative",
      origin,
      text,
      figure_refs: [],
    });
  }
  return chunks;
}

export function visionNoteToChunk(note) {
  let text = note.transcription ?? "";
  if (note.structured) text += " " + JSON.stringify(note.structured);
  const sectionId = `${note.source_ref ?? "vision"}#p${note.page ?? 0}`;
  return {
    chunk_id: `vision::${note.note_id}`,
    section_id: sectionId,
    document_id: note.source_ref ?? "",
    section_path: `${note.source_ref ?? ""} / page ${note.page ?? "?"} / ${note.kind ?? "image"}`,
    classifier: "reference",
    origin: "vision",
    text,
    figure_refs: [],
    note_id: note.note_id,
    confidence: note.confidence ?? "medium",
  };
}

export function buildIndex(sourceMap, visionNotes) {
  const chunks = [];
  for (const section of sourceMap.sections ?? []) chunks.push(...chunkSection(section));
  for (const note of visionNotes?.notes ?? []) chunks.push(visionNoteToChunk(note));

  const df = {};
  const postings = {};
  for (const c of chunks) {
    const terms = tokenize(c.text + " " + c.section_path);
    const counts = {};
    for (const t of terms) counts[t] = (counts[t] ?? 0) + 1;
    postings[c.chunk_id] = counts;
    for (const t of Object.keys(counts)) df[t] = (df[t] ?? 0) + 1;
  }
  const avgLen = Object.keys(postings).length
    ? Object.values(postings).reduce((sum, p) => sum + Object.values(p).reduce((a, b) => a + b, 0), 0) / Object.keys(postings).length
    : 0;

  return {
    run_id: sourceMap.run_id, source_map_ref: null, chunk_count: chunks.length,
    doc_count: chunks.length, avg_chunk_len: avgLen, chunks, postings, doc_freq: df,
  };
}

function bm25Score(queryTerms, chunkId, postings, df, docCount, avgLen, sectionPathTerms) {
  const counts = postings[chunkId] ?? {};
  const docLen = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  let score = 0;
  for (const t of queryTerms) {
    const f = counts[t] ?? 0;
    if (!f) continue;
    const nT = df[t] ?? 0;
    const idf = Math.log((docCount - nT + 0.5) / (nT + 0.5) + 1);
    let termScore = (idf * (f * (K1 + 1))) / (f + K1 * (1 - B + (B * docLen) / avgLen));
    if (sectionPathTerms.has(t)) termScore *= SECTION_PATH_BOOST;
    score += termScore;
  }
  return score;
}

export function expandQuery(queryTerms, brandProfile) {
  if (!brandProfile) return [...queryTerms];
  const qSet = new Set(queryTerms);
  const extra = new Set();
  for (const entry of brandProfile.messaging?.terminology ?? []) {
    const termWords = tokenize(entry.term ?? "");
    const defWords = tokenize(entry.definition ?? "");
    const overlaps = termWords.some((w) => qSet.has(w)) || defWords.some((w) => qSet.has(w));
    if (overlaps) [...termWords, ...defWords].forEach((w) => extra.add(w));
  }
  for (const [avoid, use] of Object.entries(brandProfile.tone?.preferred_terms ?? {})) {
    if (tokenize(avoid).some((w) => qSet.has(w))) tokenize(use).forEach((w) => extra.add(w));
  }
  return [...new Set([...queryTerms, ...extra])];
}

export function rrfFuse(rankings, k = 60) {
  const scores = new Map();
  for (const ranking of rankings) {
    ranking.forEach((chunkId, rank) => {
      scores.set(chunkId, (scores.get(chunkId) ?? 0) + 1 / (k + rank + 1));
    });
  }
  return [...scores.keys()].sort((a, b) => scores.get(b) - scores.get(a));
}

export function queryIndex(idx, { query = "", section = null, classifier = null, origin = null, top = 5, brandProfile = null } = {}) {
  const chunkMap = new Map(idx.chunks.map((c) => [c.chunk_id, c]));
  let candidates = idx.chunks;
  if (section) candidates = candidates.filter((c) => c.section_id === section || c.section_id.startsWith(section + "."));
  if (classifier) candidates = candidates.filter((c) => c.classifier === classifier);
  if (origin) candidates = candidates.filter((c) => c.origin === origin);
  if (!candidates.length) return [];
  const candIds = new Set(candidates.map((c) => c.chunk_id));

  if (!query) return candidates.slice(0, top);

  const queryTerms = tokenize(query);
  const rankFor = (terms) => {
    const scored = candidates
      .map((c) => [bm25Score(terms, c.chunk_id, idx.postings, idx.doc_freq, idx.doc_count, idx.avg_chunk_len, new Set(tokenize(c.section_path))), c.chunk_id])
      .filter(([s]) => s > 0);
    scored.sort((a, b) => b[0] - a[0]);
    return scored.map(([, id]) => id);
  };

  const literalRank = rankFor(queryTerms);
  const expandedTerms = expandQuery(queryTerms, brandProfile);
  const sameTerms = expandedTerms.length === queryTerms.length && expandedTerms.every((t, i) => t === queryTerms[i]);
  const fused = sameTerms ? literalRank : rrfFuse([literalRank, rankFor(expandedTerms)]);

  return fused.filter((id) => candIds.has(id)).slice(0, top).map((id) => chunkMap.get(id));
}
