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

/** The roles the module library asks for. Order matters: earlier = assigned first. */
export const ROLES = ["title-slide", "section-header", "picture", "two-content", "content"];

export const ROLE_LABELS = {
  "title-slide": "Title slide",
  "section-header": "Section divider",
  picture: "Screenshot slide",
  "two-content": "Two-column slide",
  content: "Title and content",
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
