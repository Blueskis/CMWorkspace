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
  const title =
    phs.find((p) => p.type === "ctrTitle") ?? phs.find((p) => p.type === "title") ?? null;
  const pic = phs.find((p) => p.type === "pic") ?? null;
  const bodies = bodyPlaceholders(layout)
    .slice()
    .sort((a, b) => areaFraction(b, profile.slide_size) - areaFraction(a, profile.slide_size));
  const subTitle = phs.find((p) => p.type === "subTitle") ?? null;
  return { layout, title, pic, bodies, subTitle };
}
