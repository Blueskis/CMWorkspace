# The Judgement Layer

How free text becomes a manday adjustment, why every adjustment is a write to a lever the
estimator already has, and where the line sits between a pursuit's own judgement and the
firm's shared admin configuration.

## The rule the whole design follows

**The assistant moves existing levers. It never adds a new multiplier.**

v0.4 already exposes every lever a pursuit needs: scope drivers, a line's complexity grade,
quantity, inclusion, option flag and mode of conduct, involvement split, review cycles,
localisation effort, and the delivery buffer. A judgement adjustment is a named write to
one of those, never a free-floating factor bolted on top. Two things follow from this, and
they matter more than the feature itself:

- **Every adjusted number stays explainable in the estimator's own vocabulary.** A line's
  "how this was estimated" formula still reads correctly after an adjustment, because
  nothing happened that the formula doesn't already describe.
- **Revert is exact, not approximate.** Because nothing is layered on top of the model,
  undoing an adjustment means recomputing the same model without it — not subtracting an
  estimate of its effect.

## The adjustment shape

```json
{
  "op": "set_driver",
  "target": "waves",
  "value": 5,
  "rationale": "Clause 1.1.1 onboards licensees in five named phases.",
  "confidence": "high"
}
```

| `op` | `target` | `value` |
|---|---|---|
| `set_driver` | a driver key (`waves`, `headcount`, `maturity`, …) | the new number, or the matching option for a select driver |
| `set_line_level` | a line id | `Simple`, `Standard` or `Complex` |
| `set_line_mode` | a line id | `virtual`, `blended` or `physical` |
| `set_line_qty` | a line id | the new quantity, a positive number |
| `set_line_include` | a line id | `true` / `false` |
| `set_line_optional` | a line id | `true` / `false` |
| `set_global` | one of `involvement.global`, `involvement.local`, `reviewCycles`, `localisationFactor`, `contingency` | the new number, in the same units the admin UI already uses |
| `add_line` | `global` or `local` | `{name, qty, level, archetype}` |
| `note` | — | no field moves; the rationale is recorded as an assumption |

A line id is the same `stream:catalogueId` (or custom line id) already used throughout
`estimator.html` — the assistant is shown these ids as part of the current estimate, so it
never has to guess one.

## Validation, before anything renders

`validateAdjustment()` is the single gate every proposed adjustment passes through,
regardless of whether it came from the assistant, a hand-typed test case, or anything else
that might one day generate a proposal. It refuses:

- an unknown `op`, or a `target` that doesn't resolve to a real driver, an existing line, or
  a value in the global whitelist — surfaced as **malformed**, never silently dropped or
  silently applied to the nearest plausible field;
- a value out of range for its field (qty below zero, involvement outside 0-100, an
  unrecognised complexity level or mode, `contingency` above 50) — surfaced as **out of
  range**, never clamped quietly into range;
- an empty rationale — the assistant must say *why*, every time;
- anything targeting admin configuration (see below) — surfaced as **out of scope**.

A rejected proposal never touches state at all. It is staged only in memory for the
practitioner to review; rejecting it is simply discarding that draft, so there is nothing to
undo and the estimate is byte-identical to before it was ever proposed.

## Why admin configuration is barred, not just discouraged

The hours library, the archetype × complexity matrix, rank mix, mode factors, the CM
vocabulary and the past-project effort table are **shared across every future pursuit**.
One sentence of judgement about one client — "this team is inexperienced" — must never
silently reprice the norms every other estimate in the firm draws on next.

So the judgement layer's op vocabulary structurally cannot reach them: there is no op that
writes to `taskHours`, `taskOff`, `archetypes`, `rankMix`, `modeFactors`, `vocab` or
`quotes`. `set_global`'s target whitelist is the enforcement point tests exercise directly —
a proposal naming `taskHours` or `archetypes` as a `set_global` target is refused as **out
of scope**, with the reason stated, not merely ignored.

If a judgement genuinely belongs in admin configuration — a task that's consistently wrong,
a rank mix that doesn't match how the firm actually staffs a kind of work — that's a
deliberate edit on the admin tabs, made once, considered, and not something one pursuit's
free-text note should do as a side effect.

## How a delta is computed, and why revert is exact

Every proposal is previewed against a full clone of the live estimate before it is ever
shown: apply the change to the clone, rebuild, recompute totals, diff against the real
current total. That is the number shown on the proposal card, and it is guaranteed to match
the number that actually lands once accepted — there is no separate "predicted" formula to
drift out of step with the real one.

Once accepted, an adjustment is appended to a log (`state.adjustments`) and the whole
estimate is **replayed**: rebuilt from a snapshot taken before the very first judgement
adjustment, then every still-accepted entry reapplied in the order it was accepted. This is
what makes revert exact regardless of order — reverting one entry from the middle of the log
doesn't try to subtract its effect out of what's on screen; it just drops that entry from the
replay and lets everything after it recompute fresh. Two adjustments on the same line, with
the first reverted, land exactly where accepting only the second would have.

The pre-judgement baseline plus the sum of every currently accepted entry's logged delta
always equals the current total exactly — that reconciliation is what a test in
`tests/judgement.test.js` checks directly, not asserted from the UI.

## The warning band

Accepted judgement is compared against the pre-judgement baseline on every render. Past
±40% of that baseline, a warning shows — the estimate still computes, nothing is blocked,
but a pursuit whose judgement has moved it that far is worth a second look before it goes to
a client.

## Rebuilding from scope with judgement in play

"Rebuild from scope" regenerates the deliverable line set from the current scope drivers —
which per-line adjustments (complexity, quantity, inclusion, option, mode, or a
judgement-added deliverable) cannot survive, since the lines themselves are being
regenerated. Rather than silently drop them, `rebuildFromScopeWithJudgement()` marks each
accepted per-line adjustment **superseded**: it stays visible in the log with its original
rationale, but no longer applies. Driver and global adjustments are untouched and continue
to apply on the freshly rebuilt lines.

## Degraded mode

The judgement panel calls the artifact platform's `sample` capability. When it isn't
available — `claude.use("sample")` resolves `null`, or a call rejects `not_granted` — the
panel shows a plain message and nothing else in the file is affected: every lever the
assistant would otherwise move is still there to set by hand on the Manday estimate tab.
Opened from disk with no viewer at all, the same thing happens: the estimator is fully
functional, just without the judgement assistant.
