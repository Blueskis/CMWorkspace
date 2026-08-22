# Readiness dimensions

Eight dimensions, fixed. The set is deliberately closed: the whole value of the matrix is
that a training evaluation item and a comms feedback item can land in the same cell and be
compared. A ninth dimension invented for one source breaks that.

Every quantitative and free-text item in a source adapter is mapped to exactly one of
these. If an item genuinely spans two, split it in the adapter or pick the one it
predicts, and note the call in the adapter.

| Dimension | The question it answers | Typical instrument items |
|---|---|---|
| `awareness` | Do they know this is happening, and where to find out more? | "I am kept informed about the programme", "I know where to go with questions" |
| `understanding` | Do they know what changes **for them**? | "I know what will change in my role", "New processes are defined and understood in my area" |
| `buy_in` | Do they think it is worth doing? | "I support the change", "This will make my job better", intent-to-use items |
| `skills` | Can they actually do the new thing? | "I can apply what I learned", post-training assessment scores, "the exercises reflected my real work" |
| `system_readiness` | Is the thing itself ready for them — system, process, data, access? | "My team can do their work in the new system today", access/provisioning checks, dry-run outcomes |
| `capacity` | Do they have the time and headroom to absorb it? | "I have enough time to prepare", "my team can absorb this alongside BAU" |
| `leadership_support` | Are their own leaders visibly behind it and able to answer? | "My manager has explained what this means for us", "leaders are visible and behind this" |
| `confidence` | Do they believe they will cope on day one? | "I feel confident about go-live", "I know what to do if something goes wrong" |

## Distinctions that matter in practice

**Awareness vs understanding.** Awareness is reach; understanding is relevance. The
commonest pattern in change feedback is high awareness over low understanding — the comms
machine is working and telling people about milestones instead of about their Monday. Keep
them separate or that pattern becomes invisible.

**Skills vs confidence.** Training moves skills. Confidence is moved by skills *plus*
system readiness plus capacity plus whether anyone will be there on day one. Skills up and
confidence flat is a genuine finding, and it is usually the finding: comprehension is not
the constraint.

**Capacity vs buy-in.** "I don't have time for this" is read as resistance far more often
than it is resistance. Capacity is a resourcing decision owned by operations; buy-in is a
persuasion problem owned by the programme. Mapping a capacity item to buy-in sends the
recommendation to the wrong person.

**System readiness is about the thing, not the person.** It is the only dimension that can
be red when every person is perfectly prepared, and the only one where line-manager and
technical sources usually beat self-report.

## Scoring conventions

- Everything is normalised to **0-100, higher is better**, from whatever scale the
  instrument used. The adapter declares the scale; `reverse: true` handles items where a
  high raw score is bad news ("How much extra workload do you expect?").
- Bands: green ≥ 70, amber ≥ 55, red below. These are conventional, not empirical — say so
  when a stakeholder asks, and change them in one place (`--min-n` and the band constants
  in `analyze_quant.py`) if the programme has its own.
- A base below `--min-n` (default 5) is banded *thin* and never green, however high the
  mean. Four enthusiastic responses out of 140 people is not a green cell.
- Detractor share (default: normalised ≤ 40) is reported alongside the mean, because a
  bimodal segment and a lukewarm one produce the same average and need opposite responses.
