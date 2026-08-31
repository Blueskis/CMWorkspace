# SAP Guided Buying → Word manual

Exports an SAP Help Portal guide into a single `.docx` shaped for retrieval-augmented
generation (the ElevenLabs voice-agent knowledge base).

## Why a pipeline and not a copy-paste

`help.sap.com/docs/...` is a Vue single-page app: a plain HTTP client gets an empty
shell, and headless Chromium is blocked by this environment's egress relay. The SPA's
own JSON endpoints, however, serve the real content unauthenticated:

| Endpoint | Gives you |
|---|---|
| `/http.svc/deliverableMetadata?product_url=&deliverable_url=&version=&language=&state=` | deliverable `id`, `buildNo` |
| `/http.svc/pagecontent?deliverable_id=&buildNo=` | `deliverable.fullToc` — the whole table of contents |
| `/http.svc/pagecontent?...&file_path=<loio>.html` | one topic's DITA-generated HTML |

## Regenerating

```bash
python3 tools/sap_guided_buying/fetch.py --version 2611     # next quarterly release
python3 tools/sap_guided_buying/build_docx.py --manifest tools/sap_guided_buying/manifest-<id>-2611.json
```

`fetch.py` caches every topic under `cache/<deliverable_id>-<version>/`, so re-running is
free and `build_docx.py` can be iterated offline. Pass `--refresh` to force a refetch.

To build the administrator guide instead:

```bash
python3 tools/sap_guided_buying/fetch.py \
  --deliverable-url guided-buying-administration --version 2608
```

Any SAP Help deliverable works — take `product_url` and `deliverable_url` from the two
path segments after `/docs/` in its portal URL.

## Files

- `fetch.py` — resolves the deliverable, flattens the TOC, caches every topic, writes `manifest-<id>-<version>.json`
- `convert.py` — DITA-generated HTML → flat blocks (paragraphs, list items, tables, notes, captions)
- `build_docx.py` — blocks → `deliverables/<Title>-<version>.docx`

## Choices made for RAG rather than for reading

- One Word heading per SAP topic, at the topic's own TOC depth, so chunkers split on
  semantic boundaries.
- Every section opens with a breadcrumb line, so a chunk lifted out of the middle of the
  document still states what it is about.
- Cross-references are annotated inline (`(see "X" in this manual)`); external links keep
  their URL. A bare "see below" is useless once chunked.
- Screenshots are dropped (a voice agent cannot use them); `alt` text is kept as a caption
  where SAP supplied one.
- Note/Caution/Tip labels are kept inline as text rather than as styling, so they survive
  plain-text extraction.
- Tables are real Word tables with header rows, not ASCII art.

## Attribution

The content is SAP SE's copyrighted documentation, reproduced for reference. The generated
document carries a source-and-attribution page with the version, retrieval date, and
canonical help.sap.com URL.
