"use client";

import { FORMATS, resolveColor, type Brief, type FlyerSpec } from "../spec";
import { ensureFontsLoaded } from "../fonts";
import type { Critique, CritiqueIssue } from "../types";
import { contrastRatio, luminance, renderFlyer, type RenderReport, type SourceImage } from "./render";

const CHECK_WIDTH = 900;

export function exportWidth(spec: Pick<FlyerSpec, "format">) {
  const f = FORMATS[spec.format];
  return f.print ? f.print.w * 300 : f.w;
}

export async function fontsFor(spec: FlyerSpec) {
  await ensureFontsLoaded(spec.layers.flatMap((l) => (l.type === "text" ? [{ font: l.font, weight: l.weight }] : [])));
}

export async function runChecks(
  spec: FlyerSpec,
  brief: Brief,
  images: Map<string, SourceImage>,
  verified: Map<string, boolean>,
): Promise<Critique> {
  await fontsFor(spec);
  const full = document.createElement("canvas");
  const bg = document.createElement("canvas");
  const H = Math.round((CHECK_WIDTH * FORMATS[spec.format].h) / FORMATS[spec.format].w);
  full.width = bg.width = CHECK_WIDTH;
  full.height = bg.height = H;
  const report = renderFlyer(full.getContext("2d")!, spec, images, { width: CHECK_WIDTH });
  const bgCtx = bg.getContext("2d", { willReadFrequently: true })!;
  renderFlyer(bgCtx, spec, images, { width: CHECK_WIDTH, skipTypes: ["text"] });
  const issues: CritiqueIssue[] = [];

  issues.push(...fidelityIssues(spec, report, verified));
  issues.push(...infoIssues(spec, brief));
  issues.push(...contrastIssues(report, bgCtx));
  issues.push(...sizeIssues(spec, report));

  const fonts = new Set(spec.layers.flatMap((l) => (l.type === "text" && !l.hidden ? [l.font] : [])));
  if (fonts.size > 3) issues.push({ severity: "warn", area: "Type", note: `${fonts.size} typefaces in use; traditional posters rarely use more than two.`, fix: "Use the same typeface for the small info lines" });
  else issues.push({ severity: "pass", area: "Type", note: `${fonts.size} typeface${fonts.size === 1 ? "" : "s"}, set from real font files. No generated lettering.` });

  const inks = new Set<string>([resolveColor(spec.background.color, spec.palette).toLowerCase()]);
  for (const l of spec.layers) {
    if (l.hidden) continue;
    if (l.type === "shape") inks.add(resolveColor(l.fill, spec.palette).toLowerCase());
    if (l.type === "text") inks.add(resolveColor(l.color, spec.palette).toLowerCase());
  }
  if (inks.size > 5) issues.push({ severity: "warn", area: "Colour", note: `${inks.size} flat colours; print-process palettes usually stop at 3–4.`, fix: "Reduce to paper, ink and one accent" });
  else issues.push({ severity: "pass", area: "Colour", note: `${inks.size} flat inks, no gradients or glows.` });

  const texts = spec.layers.filter((l) => l.type === "text" && !l.hidden);
  if (texts.length > 2 && texts.every((l) => l.type === "text" && l.align === "center") && !["letterpress", "psych", "tour", "ticket"].includes(spec.recipeId)) {
    issues.push({ severity: "info", area: "Composition", note: "Everything is centred. Symmetry by default is a common AI-flyer tell.", fix: "Set the info block flush left and let the photo bleed off one edge" });
  }
  if (spec.layers.length > 16) issues.push({ severity: "warn", area: "Composition", note: `${spec.layers.length} layers; risk of edge-to-edge clutter.`, fix: "Remove decorative shapes so one element dominates" });

  const penalty = issues.reduce((n, i) => n + (i.severity === "fail" ? 25 : i.severity === "warn" ? 8 : i.severity === "info" ? 2 : 0), 0);
  const fails = issues.filter((i) => i.severity === "fail").length;
  const warns = issues.filter((i) => i.severity === "warn").length;
  return {
    source: "checks",
    score: Math.max(0, 100 - penalty),
    summary: fails
      ? `${fails} blocking problem${fails > 1 ? "s" : ""} to fix before printing.`
      : warns
        ? `Print-ready with ${warns} thing${warns > 1 ? "s" : ""} worth a look.`
        : "Passes every automated check.",
    issues,
    createdAt: new Date().toISOString(),
  };
}

function fidelityIssues(spec: FlyerSpec, report: RenderReport, verified: Map<string, boolean>): CritiqueIssue[] {
  const out: CritiqueIssue[] = [];
  if (report.missingAssets.length) out.push({ severity: "fail", area: "Assets", note: "An asset in this design could not be loaded (deleted or still uploading)." });
  if (!report.fidelity.length) return out;
  const bad = report.fidelity.filter((f) => !f.uniform);
  const unverified = report.fidelity.filter((f) => verified.get(f.assetId) === false);
  if (bad.length) out.push({ severity: "fail", area: "Fidelity", note: `${bad.length} asset(s) would be stretched. Export is blocked.` });
  else if (unverified.length) out.push({ severity: "fail", area: "Fidelity", note: "An original did not match its upload fingerprint." });
  else
    out.push({
      severity: "pass",
      area: "Fidelity",
      note: `${report.fidelity.length} photo/logo placement${report.fidelity.length > 1 ? "s" : ""} at uniform scale; originals verified byte-for-byte against their SHA-256.`,
    });
  const ew = exportWidth(spec);
  for (const f of report.fidelity) {
    if (f.kind !== "photo") continue;
    const srcPerOut = f.resolution * (CHECK_WIDTH / ew);
    if (srcPerOut < 0.5) {
      out.push({
        severity: "warn",
        area: "Resolution",
        note: `The photo will be enlarged about ${(1 / srcPerOut).toFixed(1)}× at export size${FORMATS[spec.format].print ? " (300 dpi)" : ""}, so it may look soft.`,
        fix: "Zoom out on the photo or use a higher-resolution original",
      });
    }
  }
  return out;
}

function infoIssues(spec: FlyerSpec, brief: Brief): CritiqueIssue[] {
  const out: CritiqueIssue[] = [];
  const visible = spec.layers.filter((l) => !l.hidden);
  const has = (role: string) => visible.some((l) => l.type === "text" && l.role === role && l.text.trim());
  const hasBand = has("band") || visible.some((l) => l.type === "logo" && l.assetId);
  const missing = [!hasBand && "band name or logo", brief.date && !has("date") && "date", brief.venue && !visible.some((l) => l.type === "text" && l.text.includes(brief.venue)) && "venue"].filter(Boolean);
  if (missing.length) out.push({ severity: "fail", area: "Information", note: `Missing: ${missing.join(", ")}.` });
  else out.push({ severity: "pass", area: "Information", note: "Who, when and where are all on the flyer." });
  return out;
}

function sampleLuminance(ctx: CanvasRenderingContext2D, box: { x: number; y: number; w: number; h: number }, scale: number) {
  const x = Math.max(0, Math.floor(box.x * scale));
  const y = Math.max(0, Math.floor(box.y * scale));
  const w = Math.max(1, Math.min(ctx.canvas.width - x, Math.floor(box.w * scale)));
  const h = Math.max(1, Math.min(ctx.canvas.height - y, Math.floor(box.h * scale)));
  if (w <= 0 || h <= 0) return null;
  const d = ctx.getImageData(x, y, w, h).data;
  const lums: number[] = [];
  const step = Math.max(1, Math.floor((w * h) / 4000)) * 4;
  for (let i = 0; i < d.length; i += step) {
    const hex = `#${[d[i], d[i + 1], d[i + 2]].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
    lums.push(luminance(hex));
  }
  lums.sort((a, b) => a - b);
  return { median: lums[Math.floor(lums.length / 2)], p10: lums[Math.floor(lums.length * 0.1)], p90: lums[Math.floor(lums.length * 0.9)] };
}

function contrastIssues(report: RenderReport, bgCtx: CanvasRenderingContext2D): CritiqueIssue[] {
  const out: CritiqueIssue[] = [];
  let worst: { role: string; ratio: number } | null = null;
  for (const t of report.text) {
    const s = sampleLuminance(bgCtx, t.box, 1);
    if (!s) continue;
    const tl = luminance(t.color);
    // Use the least favourable of the busy parts of the background under the text.
    const ratio = Math.min(contrastRatio(tl, s.median), contrastRatio(tl, tl > 0.5 ? s.p90 : s.p10));
    const large = t.finalPx / report.width > 0.04;
    const need = large ? 3 : 4.5;
    if (ratio < need && (!worst || ratio < worst.ratio)) worst = { role: t.role, ratio };
  }
  if (worst) {
    out.push({
      severity: worst.ratio < 2 ? "fail" : "warn",
      area: "Contrast",
      note: `The ${worst.role} text has low contrast (${worst.ratio.toFixed(1)}:1) against what's behind it.`,
      fix: `Make the ${worst.role} text darker or lighter, or move it onto a plain area`,
    });
  } else if (report.text.length) {
    out.push({ severity: "pass", area: "Contrast", note: "All text clears contrast thresholds against its background." });
  }
  return out;
}

function sizeIssues(spec: FlyerSpec, report: RenderReport): CritiqueIssue[] {
  const out: CritiqueIssue[] = [];
  const f = FORMATS[spec.format];
  const band = report.text.find((t) => t.role === "band");
  const date = report.text.find((t) => t.role === "date");
  for (const t of report.text) {
    const frac = t.finalPx / report.width;
    if (f.print) {
      const pt = frac * f.print.w * 72;
      if (pt < 9) out.push({ severity: "warn", area: "Legibility", note: `The ${t.role} text prints at about ${pt.toFixed(0)} pt, too small to read from a distance.`, fix: `Make the ${t.role} text bigger` });
    } else if (frac * f.w < 22) {
      out.push({ severity: "warn", area: "Legibility", note: `The ${t.role} text is about ${Math.round(frac * f.w)} px on a phone-sized post.`, fix: `Make the ${t.role} text bigger` });
    }
    if (t.finalPx < t.requestedPx * 0.7) out.push({ severity: "info", area: "Fit", note: `The ${t.role} text was shrunk to fit its box.`, fix: `Give the ${t.role} text a bigger box or shorten it` });
  }
  if (band && date && date.finalPx < band.finalPx * 0.18) {
    out.push({ severity: "warn", area: "Hierarchy", note: "The date is much smaller than the band name; people scan for when and where next.", fix: "Make the date bigger" });
  }
  return out;
}
