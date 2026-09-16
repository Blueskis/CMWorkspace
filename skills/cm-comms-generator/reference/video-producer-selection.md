# Video producer selection — `short_form_video` / `explainer_video`

Both lanes are `planned` in `schemas/channel_registry.json` and today exit `0/handoff_only`:
`video_spec.py` writes the scene table, VO script, on-screen text and `captions.vtt`, and
that spec **is** the deliverable. This file records the vendor decision for when a producer
is actually wired — no producer is wired by this change.

Researched 2026-09-15. Pricing and certification claims move; re-verify before quoting a
client, and treat anything below without a source link as this session's best estimate, not
a checked fact.

## Correcting the record

The registry's stated blocker — "ElevenLabs installed but DISABLED IN CHAT... no
text-to-speech tool visible" (`channel_registry.json:39`) — is stale. The connector is live
in current sessions and exposes `creative_generate_speech`, `creative_generate_video`,
`creative_generate_image` and flow tools, not just voice-agent management. See the
`channel_registry.json`, `SKILL.md`, and `channel-routing.md` edits made alongside this file.

That correction does not unblock the lanes. It only removes a wrong reason. The real
blocker, restated below, is that **no avatar-video producer is installed**, and that picking
one is a client-facing security decision, not a technical one.

## What is actually three decisions, not one

| Track | What it is | Solved today? |
|---|---|---|
| Assembly | Scene order, timing, on-screen text, captions | Yes — `video_spec.py`, stays local, vendor-neutral |
| Picture | Presenter / avatar, slides, screen capture | No — this is the decision below |
| Narration | The VO read | Only where the picture vendor's own TTS is insufficient |

Assembly is not up for debate here. The open decision is the picture, and narration is a
secondary question that mostly resolves itself once the picture vendor is chosen.

## Recommendation: Synthesia for the picture, avatar's own voice for narration

Equal weight on cost, data security, and quality, plus re-promptability (can you re-prompt
and refine, or only re-roll and hope). Synthesia is the only candidate that clears a
Singapore government / GLC security review without a fight, and its editor model is genuine
refinement rather than regeneration — change the script, keep everything else, re-render.

It loses on cost and on the fact that **no MCP connector exists for it**, so wiring it means
a manual handoff step (upload `video_spec.json`'s narration + scene content to Synthesia's
own editor), not an in-chat tool call. That is consistent with how this lane already treats
Canva-without-a-Brand-Template and docx/pptx skill routes: a real producer, reached by hand
when no API path exists.

## Comparison table

| Vendor | Role | Cost (2026) | Security | Quality / re-promptability | Verdict |
|---|---|---|---|---|---|
| **Synthesia** | Avatar + picture | Free 10 min/mo watermarked; Starter $29/mo ($18 annual); Creator $89/mo ($64 annual, 30 min, 5 avatars); Enterprise custom, typically $20k–$100k+/yr; custom Studio avatar +$1,000/yr (2–3 wk lead); overage $2–$5/min ([Arcade](https://www.arcade.software/post/synthesia-pricing)) | SOC 2 Type II, ISO 27001, ISO 27701, **ISO 42001** (first AI video company certified — [A-LIGN](https://www.a-lign.com/resources/case-study-synthesia)), GDPR, EU data residency, UK Cyber Essentials ([Synthesia security](https://www.synthesia.io/legal/security-practices)) | True script-edit-and-rerender workflow; purpose-built for corporate explainer/training register | **Recommended** |
| **HeyGen** | Avatar + picture, cost alternative | Business $149/mo + $20/seat (~$7,548/yr at 25 seats); Enterprise custom ([Colossyan comparison](https://www.colossyan.com/posts/heygen-vs-synthesia/)) | SOC 2 Type II, GDPR; no published ISO 42001 | Broader avatar range, good value; repo already names its "HyperFrames" product as an uninstalled neighbour (`channel_registry.json:258-265`) | Fallback if Synthesia's price doesn't clear |
| **Colossyan** | Avatar + picture, L&D alternative | ~$19–28/mo entry ([Colossyan](https://www.colossyan.com/posts/heygen-vs-synthesia/)) | SOC 2, GDPR, SSO, data residency options; thinnest published certification depth of the three | Strongest scenario/training depth — maps well onto S/4HANA enablement content | Consider for training-heavy deliverables specifically |
| **Vyond** | Animated presenter (not photoreal) | $1,649/user/yr enterprise; SSO is a $450/user tier upgrade ([Vyond pricing](https://checkthat.ai/brands/vyond/pricing)) | SOC 2 Type II, GDPR/EU or US residency, hosted on AWS ([Vyond security](https://www.vyond.com/solutions/enterprise/security/)) | Sidesteps the likeness-consent problem below entirely by using an illustrated character, not a real face | Consider if "presenter" doesn't need to be photoreal |
| **ElevenLabs (TTS only)** | Narration, when the avatar vendor's own voice doesn't cover it | Creator $22/mo (121k credits) / Pro $99/mo (500k) / Business $1,320/mo; ~1,000 credits/min, so a 4-min explainer ≈ $0.90 ([BIGVU](https://bigvu.tv/blog/elevenlabs-pricing-2026-plans-credits-commercial-rights-api-costs/)) | Zero Retention Mode covers TTS/STT/Agents, **not voice cloning** — cloned voices persist; Enterprise defaults to no-train, offers data residency ([ElevenLabs ZRM docs](https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode)) | Best-in-class voice quality/multilingual; scope stays narration only, never the picture | Keep as a narration-only fallback |
| **ElevenLabs video generation** | — | Beta, paid-plans-only reseller layer over Sora 2 Pro / Veo 3.1 / Kling ([ElevenLabs blog](https://elevenlabs.io/blog/openai-sora)) | Adds a second and third vendor's model terms under one wrapper — wrong shape for a single DPA | Re-rolls rather than refines; can't render an accurate Fiori screen or correct go-live date | **Reject for client work** |
| **Higgsfield** | — | Starter $15 / Plus $39 / Ultra $99 / Teams $59 per seat; API $0.10/generated second ([Layer3Labs](https://www.layer3labs.io/guides/higgsfield-ai-pricing)) | Enterprise claims "SOC 2-**aligned**" (not certified), GDPR, SSO, contractual no-train ([Higgsfield privacy](https://geo.higgsfield.ai/blog/recommended/is-higgsfield-ai-safe-for-privacy-and-data-934019)) | Consumer-facing platform (ships `tiktok_publish`, `virality_predictor`); not built for enterprise deliverables | **Reject for client work** — fine for internal CoE marketing only |
| **Veo 3.1 (Vertex AI)** | Named, not recommended | $0.15/s Fast, $0.40/s Standard, $0.75/s Full ([CometAPI](https://www.cometapi.com/how-much-does-veo-3-cost-all-you-need-to-know/)) | Only option with a genuine **Singapore data residency** story — Google Cloud's SG region now stores data at-rest and runs ML processing in-country; Vertex does not train on customer data without permission ([Singapore EDB](https://www.edb.gov.sg/en/about-edb/media-releases-publications/google-cloud-expands-gemini-ai-strengthens-singapore-focus.html)) | No branded presenter; same determinism problem as other generative video | Answer for "residency is non-negotiable", not for "we need a presenter" |
| **Canva** | Secondary route, already integrated | Existing enterprise contract | SOC 2 Type II, ISO 27001, data residency, Canva Shield, enterprise indemnity ([Cyber Magazine](https://cybermagazine.com/news/how-canva-embeds-security-and-ai-in-enterprise-platforms)) | Same `generate-design` verbatim-copy defect already logged at `channel_registry.json:194` | Fits the brief-plus-Brand-Template pattern `canva_brief.py` already implements |

## The decisive risk isn't where the script text goes — it's the avatar itself

A custom avatar built from a named client executive's face and voice is **biometric
personal data**, not ordinary marketing content:

- **Singapore PDPA s13**: consent is required before collection and use, and it must be
  specific to the AI use case — an employer cannot repurpose footage collected for another
  purpose to build an avatar ([BusinessPlusAI](https://www.businessplusai.com/blog/singapore-pdpa-and-ai-complete-compliance-guide-for-employers)).
- **GDPR Art. 9** treats it as a special category requiring explicit consent.
- The real exposure is what happens to the source facial/voice recording — retention, who
  can access it, whether it survives the person's offboarding or departure from the client.

This mirrors the framing already used for cloud ASR in
`skills/change-impact-assessment/reference/audio-workflow.md:41-52`: **this is a decision for
the engagement lead and the client's DPO, not a technical convenience.** Raise it before
committing to any avatar vendor, every time a real person's likeness is involved. A
**stock/library avatar** (not modeled on a named individual) sidesteps this entirely and
should be the default unless the client specifically wants their own presenter.

**Separately:** Synthesia, HeyGen and Colossyan all publish EU/US data residency only — none
publish Singapore or APAC residency. For an IM8-governed agency this may be disqualifying
regardless of certification depth. Put the residency question to the client's security team
*before* proposing any of these three, alongside the consent question above.

## Two lanes, chosen per engagement (narration egress is switchable, not fixed)

- **Cloud avatar lane** — `video_spec.json` becomes the handoff into Synthesia (or chosen
  alternative). Script and any likeness leave the firm's environment. Preconditions: signed
  DPA, PDPA consent for any named-individual avatar, residency question answered by the
  client's security team.
- **Local lane** — `video_spec.json` + brand-applied HTML (existing `render_comms_html.py`
  pattern) + offline TTS or a silent render carrying `captions.vtt`. Nothing leaves the
  machine. Register shifts to animated slides / kinetic typography rather than a presenter.
  This is the lane for a client that will not clear cloud avatar rendering at all.

Record which lane an engagement uses as a gating fact, the same way `brand_profile.json`
already gates a Canva Brand Template ID (`brand_profile.schema.json:144-169`).

## One register caution

`reference/channel-library.md:205-253` already names "a talking head with no screen
capture, which is a video of a memo" as the explainer failure mode. An avatar-led picture
works well for the hook and the "why this, why now" chapter of an explainer, and for
short-form generally — but the per-task chapters of an explainer still need real screen
capture of the Fiori UI. Treat the recommendation as **hybrid** (avatar intro/outro + real
screen capture for task steps), not a pure talking head end to end.

## What this does not decide

No producer is wired into `route_channel.py` by this file. Both lanes remain
`0/handoff_only` until a follow-up change implements the cloud or local lane above, taken
after the client's security and consent questions in this file come back answered.
