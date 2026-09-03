"use strict";

/* =================================================================
   Export — offers the built .pptx via the downloads capability, with
   a required fallback: .pptx sits in the EXTENDED download extension
   set (gif png jpg jpeg webp mp4 webm txt json md is the base set;
   docx pptx epub csv ttf html svg pdf is extended and may not be
   enabled for a given viewer). Whether it's enabled can only be
   discovered by the call itself rejecting extension_not_enabled, so
   the fallback is not optional polish — it is how this ever reaches
   a viewer without extended types on.
   ================================================================= */

const MAX_BYTES = 16 * 1024 * 1024; // downloads.save's own limit

function planJson(plan) {
  return JSON.stringify(plan, null, 2);
}

function planMarkdown(plan) {
  const lines = [`# ${plan.engagementTitle || "Proposal draft"}`, ""];
  for (const slide of plan.slides || []) {
    lines.push(`## ${slide.title}`);
    if (slide.layoutHint) lines.push(`*Layout: ${slide.layoutHint}*`, "");
    for (const block of slide.blocks || []) {
      if (block.gap) {
        lines.push(`> [GAP] ${block.gap_note || ""}`);
      } else if (Array.isArray(block.items)) {
        for (const item of block.items) lines.push(`${"  ".repeat(item.level || 0)}- ${item.text}`);
      } else if (block.text) {
        lines.push(block.text);
      }
      if (block.sources && block.sources.length) lines.push(`_sources: ${block.sources.join(", ")}_`);
      lines.push("");
    }
  }
  return lines.join("\n");
}

/* downloads: the claude.use("downloads") namespace (or a fake in
   tests). pptxBuffer may be null when the build itself failed or
   hasn't run — callers should not invoke export in that case, but
   this function still degrades safely rather than throwing. Returns
   a status object the UI can render directly, never throws for an
   expected downloads-capability rejection. */
async function exportProposal(downloads, { pptxBuffer, filenameBase, plan }) {
  if (pptxBuffer && pptxBuffer.byteLength > MAX_BYTES) {
    return {
      status: "too_large",
      message: `The generated .pptx is ${(pptxBuffer.byteLength / 1024 / 1024).toFixed(1)} MB, `
        + `over the 16 MB download limit. Remove a slide or an oversized past-deck excerpt and try again.`,
    };
  }

  if (pptxBuffer) {
    try {
      await downloads.save({ filename: `${filenameBase}.pptx`, data: pptxBuffer });
      return { status: "saved", format: "pptx" };
    } catch (err) {
      const code = err && err.code;
      if (code === "declined") {
        return { status: "declined", message: "Download was not confirmed. Nothing was saved." };
      }
      if (code !== "extension_not_enabled" && code !== "rejected_extension") {
        return { status: "error", message: (err && err.message) || String(err), code };
      }
      // Fall through to the .json + .md fallback below.
    }
  }

  const jsonBytes = new TextEncoder().encode(planJson(plan));
  const mdBytes = new TextEncoder().encode(planMarkdown(plan));
  try {
    await downloads.save({ filename: `${filenameBase}.json`, data: jsonBytes });
    await downloads.save({ filename: `${filenameBase}.md`, data: mdBytes });
    return {
      status: "saved",
      format: "json+md",
      message: ".pptx downloads are not enabled for this view, so the draft was saved as "
        + "the plan schema (.json) and a readable outline (.md) instead. Build the deck with "
        + "the pptx skill's template workflow from the .json.",
    };
  } catch (err) {
    const code = err && err.code;
    if (code === "declined") {
      return { status: "declined", message: "Download was not confirmed. Nothing was saved." };
    }
    return { status: "error", message: (err && err.message) || String(err), code };
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { exportProposal, planJson, planMarkdown, MAX_BYTES };
}
