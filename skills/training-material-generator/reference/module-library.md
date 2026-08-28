# Module library

The canonical modules a system-training deck is built from, in the order they usually run.
Each entry says what the module is for, when to include it, what it needs from the source
documents, its typical slide count, and which audiences it serves.

These are **internal handles, not slide titles.** Slide titles use the client's and the
system's own words — see Rule 1 in SKILL.md.

Not every module appears in every deck. Include one when the documents support it and the
objectives need it; leave it out otherwise. A module included with nothing to say is worse
than a module missing.

---

## `title`
**Purpose** Name the course, the system and the release.
**Include** Always.
**Needs** The system name and the release. Both from the specification's front matter.
**Slides** 1 · `title-slide`
**Audiences** all

## `why-this-matters`
**Purpose** What changes for the learner, and why the change was made.
**Include** When the specification says what the new system replaces, or when the change is
disruptive enough that people will arrive resistant.
**Needs** The purpose/background section. If the specification only describes the new system
and never says what it replaces, this is a `[GAP]` worth raising — the change story usually
lives with the project, not the spec.
**Slides** 1 · `title-and-content` or `two-content` (before / after)
**Audiences** all

## `learning-objectives`
**Purpose** What the learner will be able to do by the end.
**Include** Always.
**Needs** Nothing from the documents — these are written in Stage 2 from the objectives.
**Slides** 1 · `objectives`
**Audiences** all

## `agenda`
**Purpose** How the session runs and how long each part takes.
**Include** For any session over about 30 minutes.
**Needs** The module plan and its durations.
**Slides** 1 · `agenda`
**Audiences** all

## `process-context`
**Purpose** The end-to-end process the system supports, before any screen appears.
**Include** Almost always. This is the module that stops the deck being clicks without a why.
**Needs** The process overview or lifecycle section; a status/state list if there is one.
Usually the best candidate for a generated diagram — see `diagram-patterns.md`.
**Slides** 1–3 · `diagram`, `table`, `title-and-content`
**Audiences** all

## `roles-and-responsibilities`
**Purpose** Who can do what, and — more usefully — who cannot.
**Include** Whenever more than one role touches the process.
**Needs** The roles section. The "cannot do" column is the one learners need and the one
specifications most often leave implicit; derive it from the permissions text and cite it.
**Slides** 1 · `role-grid`
**Audiences** all

## `key-concepts-and-terms`
**Purpose** The handful of terms the rest of the deck depends on.
**Include** When the system introduces vocabulary the business does not already use.
**Needs** A glossary, or definitions embedded in the prose.
**Slides** 1–2 · `table`, `two-content`
**Audiences** all
**Watch** Keep it to terms that appear later in the deck. A glossary of everything is a
reference document, not a training module.

## `system-walkthrough`
**Purpose** How to actually do the task, screen by screen.
**Include** One module per major transaction or screen the audience performs. This is the
core of the deck and usually most of its length.
**Needs** The screen description, its screenshots, and the field rules. A walkthrough with no
capture is a walkthrough of an imaginary screen — if the specification has no screenshot for
a screen you must teach, that is a `[GAP]` and someone needs to capture one.
**Slides** 2–5 each · `screenshot-walkthrough`, `screenshot-full`, `table`,
`title-and-content`
**Audiences** the role that performs the task — this is where the v0.2 audience split bites
hardest, so record it carefully

## `business-rules-and-validations`
**Purpose** The rules the system enforces and the messages it shows when they are broken.
**Include** Whenever the specification states validations, thresholds or mandatory fields.
**Needs** The field-rules and validation tables. Reproduce values and field names verbatim —
never round a threshold, never turn "must be today or later" into "must be a future date".
**Slides** 1–3 · `table`, `title-and-content`
**Audiences** the role the rules constrain

## `exceptions-and-error-handling`
**Purpose** What to do when it does not go to plan.
**Include** Whenever the specification has an exceptions section — and it usually does,
buried at the end of a chapter.
**Needs** The exception paths. Where an exception ends with "contact an administrator",
check the deck actually names who that is; if it does not, that is a `[GAP]` worth flagging
loudly, because it is the one people hit under pressure.
**Slides** 1–2 · `title-and-content`, `two-content`
**Audiences** all who perform the task

## `integrations-and-downstream-impact`
**Purpose** What happens elsewhere as a result of what the learner just did.
**Include** When the specification describes postings, interfaces or downstream systems.
This is what makes people careful — a learner who knows an issued order commits budget
treats it differently.
**Needs** The integrations section.
**Slides** 1 · `title-and-content`, `diagram`
**Audiences** all

## `knowledge-check`
**Purpose** Check the module landed, before moving on.
**Include** At the end of every substantive module — walkthroughs, rules, exceptions.
**Needs** The module's own content. **Exactly five questions, mixed multiple-choice and
True/False** — see `question-writing.md`.
**Slides** 1 · `knowledge-check`
**Audiences** the module's audience
**Watch** If a module cannot yield five real questions it is too thin; merge it into its
neighbour at Stage 2 rather than padding here.

## `recap`
**Purpose** The handful of things to remember, matched back to the objectives.
**Include** Always.
**Needs** The deck itself. Put the objectives slide back up beside it.
**Slides** 1 · `recap`
**Audiences** all

## `where-to-get-help`
**Purpose** Who to contact, which queue, what to have ready.
**Include** Always.
**Needs** Support routes — which specifications almost never contain. Expect this to be a
`[GAP]` on the first draft, and say so at handover: it is the slide learners photograph.
**Slides** 1 · `support`
**Audiences** all

---

## Typical shapes

**Short awareness session (~30 min, 8–10 slides)** — title, learning-objectives,
process-context, roles-and-responsibilities, one system-walkthrough, knowledge-check, recap,
where-to-get-help.

**Full end-user course (~2 hours, 20–30 slides)** — title, why-this-matters,
learning-objectives, agenda, process-context, roles-and-responsibilities,
key-concepts-and-terms, two or three system-walkthroughs each with
business-rules-and-validations and a knowledge-check, exceptions-and-error-handling,
integrations-and-downstream-impact, recap, where-to-get-help.

**Approver-only session (~45 min)** — title, learning-objectives, process-context (their
part of it), the approval walkthrough, business-rules-and-validations for thresholds,
exceptions-and-error-handling, knowledge-check, recap, where-to-get-help. In v0.1 this is a
separate run with a narrower objective set; in v0.2 it will be an audience filter over one
plan, which is why `audiences` is recorded now.
