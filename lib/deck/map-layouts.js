/**
 * Decide which of an unknown template's layouts each kind of slide should use.
 *
 * This has no equivalent in the Python pipeline, which was pointed at one known template
 * and carried a hand-written layout table. Here the template arrives at runtime, so the
 * mapping has to be derived — and derived from each layout's PLACEHOLDER SIGNATURE, not
 * its name. Client templates name layouts unpredictably ("Content 1 / 2 / 3", localised
 * names, "Slide Layout 7"), so a name-based guess is unreliable in exactly the case this
 * feature exists for.
 *
 * The mapping is a proposal. The UI shows it and lets the user override before anything
 * is built — a wrong guess caught here costs one dropdown, and caught later costs a deck.
 */

/**
 * The roles a slide can be assigned. Order matters: earlier = assigned first, so a layout
 * that would satisfy two roles equally well goes to whichever role is listed first.
 *
 * The first five are the original training-deck set. The rest widen this to general
 * consulting decks (steerco updates, findings decks, case-for-change, workshop packs) —
 * added when deck-builder generalised this module out of the training-only pipeline.
 * Most real templates have no dedicated layout for the new roles; resolveLayoutRoles()
 * degrades them onto the closest existing layout exactly as it already did for `picture`
 * and `two-content`, and the mapping is always shown to the user for override before build.
 */
export const ROLES = [
  "title-slide", "section-header", "picture", "two-content", "content",
  "comparison", "table", "metric-row", "quote", "timeline", "closing",
];

export const ROLE_LABELS = {
  "title-slide": "Title slide",
  "section-header": "Section divider",
  picture: "Screenshot slide",
  "two-content": "Two-column slide",
  content: "Title and content",
  comparison: "Side-by-side comparison",
  table: "Table",
  "metric-row": "Metrics / stat row",
  quote: "Pull quote / callout",
  timeline: "Timeline / process",
  closing: "Closing / thank-you",
};

function bodyPlaceholders(layout) {
  // 'body' is the common case; real templates also use 'obj'/'tx' for the same job.
  return layout.placeholders.filter((p) => ["body", "obj", "tx"].includes(p.type));
}

function areaFraction(ph, slideSize) {
  if (!ph.geometry || !slideSize.w_in || !slideSize.h_in) return 0;
  return (ph.geometry.w_in * ph.geometry.h_in) / (slideSize.w_in * slideSize.h_in);
}

/**
 * Score one layout for every role. Higher is better; 0 means unsuitable.
 * Returns { scores: {role: n}, best: role|null, reasons: {role: string} }
 */
export function classifyLayout(layout, slideSize) {
  const phs = layout.placeholders;
  const scores = {};
  const reasons = {};

  if (phs.length === 0) {
    return { scores, best: null, reasons: { _: "no placeholders — cannot be filled" } };
  }

  const hasCtrTitle = phs.some((p) => p.type === "ctrTitle");
  const hasTitle = phs.some((p) => p.type === "title");
  const hasSubTitle = phs.some((p) => p.type === "subTitle");
  const pics = phs.filter((p) => p.type === "pic");
  const bodies = bodyPlaceholders(layout);
  const biggestBody = bodies
    .map((b) => areaFraction(b, slideSize))
    .reduce((a, b) => Math.max(a, b), 0);

  // --- title-slide -------------------------------------------------------
  if (hasCtrTitle) {
    scores["title-slide"] = 100;
    reasons["title-slide"] = "has a centred title placeholder";
  } else if (hasTitle && hasSubTitle) {
    scores["title-slide"] = 80;
    reasons["title-slide"] = "has a title and a subtitle";
  } else if (!hasTitle && pics.length === 0 && bodies.length >= 1 && bodies.length <= 2) {
    // Some real templates (export-tool artifacts, not hand-typed) leave a layout's title
    // and subtitle as generic body/obj/tx placeholders instead of title/ctrTitle/subTitle.
    // A layout like that is still recognisable by geometry: a wide text box sitting in the
    // slide's upper half reads as a title regardless of what its XML calls it. Scored well
    // below the typed cases above so a template that types its placeholders correctly is
    // never second-guessed by this fallback.
    const topBody = bodies.reduce((best, b) => {
      const g = b.geometry;
      if (!g) return best;
      return !best || g.y_in < best.geometry.y_in ? b : best;
    }, null);
    const g = topBody?.geometry;
    const inUpperHalf = g && g.y_in + g.h_in / 2 < slideSize.h_in * 0.5;
    const isWide = g && slideSize.w_in && g.w_in / slideSize.w_in > 0.4;
    if (inUpperHalf && isWide) {
      scores["title-slide"] = 55;
      reasons["title-slide"] = "a top-positioned text placeholder, not explicitly typed as a title";
    }
  }

  // --- picture -----------------------------------------------------------
  if (pics.length > 0) {
    // Prefer a layout with ONE picture slot and a caption over a multi-picture collage.
    scores.picture = pics.length === 1 ? 100 : 60;
    reasons.picture =
      pics.length === 1
        ? "has a single picture placeholder"
        : `has ${pics.length} picture placeholders (collage layout)`;
    if (pics.length === 1 && bodies.length >= 1) {
      scores.picture += 10;
      reasons.picture += " with a caption slot";
    }
  }

  // --- two-content -------------------------------------------------------
  if (hasTitle && bodies.length >= 2 && pics.length === 0) {
    scores["two-content"] = 90;
    reasons["two-content"] = `title plus ${bodies.length} content areas`;
  }

  // --- content -----------------------------------------------------------
  if (hasTitle && bodies.length >= 1 && pics.length === 0) {
    if (biggestBody >= 0.45) {
      scores.content = 100 - Math.round((bodies.length - 1) * 15);
      reasons.content = `title plus a content area covering ${Math.round(biggestBody * 100)}% of the slide`;
    } else if (biggestBody > 0) {
      scores.content = 40;
      reasons.content = `title plus a small content area (${Math.round(biggestBody * 100)}% of the slide)`;
    } else {
      // No geometry recorded — still usable, just unranked.
      scores.content = 50;
      reasons.content = "title plus a content area (no size recorded)";
    }
  }

  // --- section-header ----------------------------------------------------
  if (hasTitle && !hasCtrTitle && pics.length === 0) {
    if (bodies.length === 0) {
      scores["section-header"] = 95;
      reasons["section-header"] = "title only";
    } else if (biggestBody > 0 && biggestBody < 0.25) {
      scores["section-header"] = 85;
      reasons["section-header"] = "title with a small strapline area";
    }
  }

  // --- comparison ---------------------------------------------------------
  // A stricter two-content: 2-3 bodies of roughly EQUAL size (side-by-side columns), not
  // just "at least two content areas" — scored above two-content so a template with a
  // layout purpose-built for this (common in consulting decks: "before/after", "options")
  // wins the slot when one exists, without ever reading the layout's own name.
  if (hasTitle && pics.length === 0 && (bodies.length === 2 || bodies.length === 3)) {
    const areas = bodies.map((b) => areaFraction(b, slideSize)).filter((a) => a > 0);
    const balanced = areas.length === bodies.length &&
      Math.max(...areas) - Math.min(...areas) < 0.12;
    scores.comparison = balanced ? 95 : 70;
    reasons.comparison = balanced
      ? `title plus ${bodies.length} evenly-sized content areas`
      : `title plus ${bodies.length} content areas (uneven sizing)`;
  }

  // --- table -----------------------------------------------------------
  const tbls = phs.filter((p) => p.type === "tbl");
  if (tbls.length > 0) {
    scores.table = 100;
    reasons.table = "has a native table placeholder";
  } else if (hasTitle && bodies.length >= 1) {
    scores.table = 35;
    reasons.table = "no table placeholder — a table would render into the content area";
  }

  // --- metric-row --------------------------------------------------------
  const charts = phs.filter((p) => p.type === "chart");
  if (charts.length > 0) {
    scores["metric-row"] = 90;
    reasons["metric-row"] = "has a native chart placeholder";
  } else if (hasTitle && bodies.length >= 3) {
    // 3+ same-row content areas reads as a stat-row shape even with no chart placeholder.
    const areas = bodies.map((b) => areaFraction(b, slideSize)).filter((a) => a > 0);
    if (areas.length >= 3 && Math.max(...areas) < 0.3) {
      scores["metric-row"] = 75;
      reasons["metric-row"] = `${bodies.length} small content areas — reads as a stat row`;
    }
  }

  // --- quote ---------------------------------------------------------------
  // No title, one substantial body, no picture — the pull-quote/callout shape. Distinct
  // from section-header (title, no/small body) and content (title present).
  if (!hasTitle && !hasCtrTitle && pics.length === 0 && bodies.length === 1) {
    const area = areaFraction(bodies[0], slideSize);
    if (area === 0 || area >= 0.3) {
      scores.quote = 80;
      reasons.quote = "a single large untitled text area — reads as a quote/callout slide";
    }
  }

  // --- timeline --------------------------------------------------------
  // No native OOXML placeholder type maps to "timeline" — this always degrades to content
  // in resolveLayoutRoles(); render-diagram.js draws the timeline as native shapes over it.
  // Scored here anyway (low) so an explicit picture-free wide-body layout is still preferred
  // over an arbitrary one when several content-shaped layouts exist.
  if (hasTitle && pics.length === 0 && biggestBody >= 0.5) {
    scores.timeline = 30;
    reasons.timeline = "wide content area — diagram shapes are drawn over this at build time";
  }

  // --- closing -----------------------------------------------------------
  // Reuses the title-slide signature: a closing/thank-you slide is visually a second title
  // slide. Always falls back onto title-slide's own resolution in resolveLayoutRoles().
  if (hasCtrTitle) {
    scores.closing = 60;
    reasons.closing = "centred title placeholder — reusable as a closing slide";
  }

  let best = null;
  let bestScore = 0;
  for (const [role, score] of Object.entries(scores)) {
    if (score > bestScore) {
      bestScore = score;
      best = role;
    }
  }
  return { scores, best, reasons };
}

/**
 * Resolve every role to a concrete layout.
 *
 * Degrades rather than failing: a template with no picture layout still produces a deck,
 * with screenshots positioned into the content layout's body geometry as free-floating
 * pictures (`pictureFallback`), which is exactly what the Python path does when
 * `layouts_with_picture_placeholder` is empty.
 */
export function resolveLayoutRoles(profile) {
  const slideSize = profile.slide_size;
  const classified = profile.layouts.map((l) => ({
    layout: l,
    ...classifyLayout(l, slideSize),
  }));

  const assignment = {};
  const notes = [];

  for (const role of ROLES) {
    const candidates = classified
      .filter((c) => (c.scores[role] ?? 0) > 0)
      .sort((a, b) => b.scores[role] - a.scores[role]);
    if (candidates.length > 0) {
      assignment[role] = {
        part: candidates[0].layout.part,
        name: candidates[0].layout.name,
        score: candidates[0].scores[role],
        reason: candidates[0].reasons[role],
        auto: true,
      };
    } else {
      assignment[role] = null;
    }
  }

  // --- fallbacks ---------------------------------------------------------
  const contentFallback = assignment.content ?? assignment["two-content"] ?? assignment["section-header"];

  if (!assignment.content && contentFallback) {
    assignment.content = { ...contentFallback, auto: false, reason: "no dedicated content layout — reusing this one" };
    notes.push("No title-and-content layout was found; another layout is standing in for body slides.");
  }

  let pictureFallback = false;
  if (!assignment.picture) {
    if (assignment.content) {
      assignment.picture = {
        ...assignment.content,
        auto: false,
        reason: "no picture placeholder in this template — screenshots are placed into the content area",
      };
      pictureFallback = true;
      notes.push(
        "This template has no picture placeholder. Screenshots will still be placed, " +
          "sized to fit the content area, but not into a native picture slot."
      );
    } else {
      notes.push("No layout can hold a screenshot; screenshot slides will be skipped.");
    }
  }

  if (!assignment["two-content"] && assignment.content) {
    assignment["two-content"] = { ...assignment.content, auto: false, reason: "no two-column layout — using the content layout" };
  }
  if (!assignment["section-header"] && assignment.content) {
    assignment["section-header"] = { ...assignment.content, auto: false, reason: "no section-divider layout — using the content layout" };
  }
  if (!assignment["title-slide"]) {
    if (assignment["section-header"] ?? assignment.content) {
      assignment["title-slide"] = {
        ...(assignment["section-header"] ?? assignment.content),
        auto: false,
        reason: "no title layout — using the closest available",
      };
      notes.push("No title-slide layout was found; the cover uses the closest match.");
    }
  }

  // --- new-role fallbacks: each degrades onto the closest already-resolved role rather
  // than failing the mapping outright, exactly like the picture/two-content fallbacks
  // above. A fallback is always marked auto: false so the plan-time variety gate and the
  // UI both know this role is borrowing another layout, not using one built for it.
  if (!assignment.comparison && assignment["two-content"]) {
    assignment.comparison = { ...assignment["two-content"], auto: false, reason: "no comparison layout — using the two-column layout" };
  }
  if (!assignment.table && assignment.content) {
    assignment.table = { ...assignment.content, auto: false, reason: "no table placeholder — table renders into the content area" };
    notes.push("No native table placeholder in this template; tables render as a drawn grid into the content area.");
  }
  if (!assignment["metric-row"] && (assignment["two-content"] ?? assignment.content)) {
    assignment["metric-row"] = { ...(assignment["two-content"] ?? assignment.content), auto: false, reason: "no metric-row layout — using the closest content layout" };
  }
  if (!assignment.quote && (assignment["section-header"] ?? assignment.content)) {
    assignment.quote = { ...(assignment["section-header"] ?? assignment.content), auto: false, reason: "no quote/callout layout — using the closest available" };
  }
  if (!assignment.timeline && assignment.content) {
    assignment.timeline = { ...assignment.content, auto: false, reason: "no timeline layout — diagram shapes are drawn over the content layout" };
  }
  if (!assignment.closing && assignment["title-slide"]) {
    assignment.closing = { ...assignment["title-slide"], auto: false, reason: "no closing layout — reusing the title-slide layout" };
  }

  if (!assignment.content && !assignment["title-slide"]) {
    throw new Error(
      "None of this template's layouts have usable placeholders, so no slide can be " +
        "filled. Check you uploaded a PowerPoint template rather than a finished deck."
    );
  }

  // The diagram host is the content layout — diagrams need one large body area.
  assignment.diagram = assignment.content
    ? { ...assignment.content, auto: false, reason: "diagrams are drawn into the content area" }
    : null;

  return { assignment, classified, notes, pictureFallback };
}

/**
 * The body/pic placeholder a given role's slides should fill, plus its geometry.
 * build-pptx uses this instead of a hardcoded per-template table.
 */
export function targetPlaceholders(profile, layoutPart) {
  const layout = profile.layouts.find((l) => l.part === layoutPart);
  if (!layout) return null;
  const phs = layout.placeholders;
  let title = phs.find((p) => p.type === "ctrTitle") ?? phs.find((p) => p.type === "title") ?? null;
  const pic = phs.find((p) => p.type === "pic") ?? null;
  // Plain x-ascending broke a real template (test/fixtures/templates/real-training-
  // template.pptx): its "content" layout has ONE big content placeholder plus one small,
  // unrelated text strip sitting a hair to its left (x 0.45 vs 0.46in) — x-ascending put
  // the tiny strip in bodies[0], so a "body" block landed in a 0.43in-tall box instead of
  // the real content area. Pure area-descending (the old comparator) has the opposite
  // problem: on a genuine two-column layout, two SIMILARLY SIZED placeholders sitting side
  // by side sort in whichever order they happen to be a few square inches bigger, not by
  // which one is actually on the left — composeSlide then indexes bodies[0]/[1] as "left
  // column"/"right column" arbitrarily.
  //
  // Only sort by x when the two placeholders are close enough in area to plausibly be
  // column-peers in the same row (a real two-content layout); otherwise a placeholder
  // meaningfully bigger than the rest is almost certainly the primary content area
  // regardless of its x position (a small secondary strip, caption slot, or footer-ish
  // placeholder should never outrank it), so area-descending still wins. A placeholder
  // with no recorded geometry sorts last, stably, rather than reordering the others.
  const AREA_PEER_TOLERANCE = 0.15; // fraction of the larger area the two must be within
  let bodies = bodyPlaceholders(layout)
    .slice()
    .sort((a, b) => {
      const areaA = areaFraction(a, profile.slide_size);
      const areaB = areaFraction(b, profile.slide_size);
      const arePeers = areaA > 0 && areaB > 0 && Math.abs(areaA - areaB) / Math.max(areaA, areaB) < AREA_PEER_TOLERANCE;
      if (arePeers) {
        const ax = a.geometry?.x_in, bx = b.geometry?.x_in;
        if (ax == null && bx == null) return 0;
        if (ax == null) return 1;
        if (bx == null) return -1;
        return ax - bx;
      }
      return areaB - areaA;
    });
  const subTitle = phs.find((p) => p.type === "subTitle") ?? null;

  if (!title && !subTitle && bodies.length >= 1) {
    // Mirrors classifyLayout's geometric title fallback (see the comment there): a layout
    // can be CHOSEN for the title-slide role via that fallback even though none of its
    // placeholders are typed title/ctrTitle/subTitle — without this, such a layout would
    // have nowhere to put the "title" slot's content at all, and it would silently drop.
    // The topmost body/obj/tx placeholder stands in for the title; whatever's left (if
    // anything) is still available for "subtitle"/"body" via the normal bodies[] lookup.
    const topmost = bodies.reduce(
      (best, b) => (!best || (b.geometry?.y_in ?? Infinity) < (best.geometry?.y_in ?? Infinity) ? b : best),
      null
    );
    const g = topmost?.geometry;
    const inUpperHalf = g && profile.slide_size?.h_in && g.y_in + g.h_in / 2 < profile.slide_size.h_in * 0.5;
    if (inUpperHalf) {
      title = topmost;
      bodies = bodies.filter((b) => b !== topmost);
    }
  }

  return { layout, title, pic, bodies, subTitle };
}
