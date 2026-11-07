import type { Layer } from "./spec.ts";
import { FORMATS } from "./spec.ts";
import {
  bandMark,
  compact,
  copy,
  frame,
  joinLines,
  mulberry32,
  photoAspect,
  photoLayer,
  rect,
  shape,
  textLayer,
  treatmentFor,
  type AssetRef,
  type BuildInput,
  type Ctx,
  type Recipe,
} from "./kit.ts";
import { BILL_RECIPES, CUSTOM_BILL } from "./bill.ts";
import type { FlyerSpec } from "./spec.ts";

export { formatDate, mulberry32, usefulHeadline, type AssetRef, type BuildInput, type Recipe, type RecipeVariant } from "./kit.ts";

// ---------- recipes ----------

const swiss: Recipe = {
  id: "swiss",
  name: "Swiss Grid",
  tagline: "Strict grid, flush-left grotesk, one accent",
  description:
    "International Typographic Style. Black-and-white photo used as a shape, flush-left type, one accent block and an info table on a modular grid.",
  palettes: [
    { paper: "#ECEAE4", ink: "#111111", accent: "#E3311D", accent2: "#8C8C8C" },
    { paper: "#F1EFE9", ink: "#141414", accent: "#1F4FD8", accent2: "#9A9A9A" },
    { paper: "#121212", ink: "#F1EFE9", accent: "#F2C200", accent2: "#5A5A5A" },
  ],
  fontPairs: [
    { display: "Inter", text: "Inter" },
    { display: "Archivo Black", text: "Libre Franklin" },
    { display: "Work Sans", text: "Work Sans" },
  ],
  treatments: ["mono", "original", "duotone"],
  mirrorable: true,
  variants: [
    { id: "inset", label: "Photo inset on the grid" },
    { id: "bleed", label: "Photo bleeds off the top" },
  ],
  build(ctx) {
    const c = copy(ctx);
    const m = 0.06;
    const mY = m / ctx.ar;
    const bleed = ctx.variant === "bleed";
    const p = bleed ? frame(ctx, 0, 0, 1, 0.52, "left") : frame(ctx, m, mY, 1 - 2 * m, 0.5, "left");
    const top = p.y + p.h;
    const bottom = 1 - mY;
    const R = bottom - top;
    const bandY = top + R * 0.05;
    const bandH = R * 0.34;
    const ruleY = bandY + bandH + R * 0.03;
    const dateY = ruleY + R * 0.04;
    const dateH = R * 0.2;
    const infoY = dateY + dateH + R * 0.04;
    const infoH = bottom - infoY;
    const col = (1 - 2 * m - 0.04) / 2;
    return {
      background: {
        color: "$paper",
        textures: [{ kind: "grain", color: "$ink", opacity: 0.08, scale: 1 }],
      },
      layers: compact<Layer>([
        photoLayer(ctx, p.x, p.y, p.w, p.h),
        c.headline && rect(ctx, 1 - m - 0.36, top - 0.03, 0.36, 0.075, "$accent", { name: "accent block" }),
        c.headline &&
          textLayer(ctx, { role: "kicker", text: c.headline, x: 1 - m - 0.34, y: top - 0.02, w: 0.32, h: 0.055, size: 0.032, weight: 600, color: "$paper", valign: "middle", font: ctx.fonts.text }),
        bandMark(ctx, m, bandY, 1 - 2 * m, bandH, { tracking: -0.02, font: ctx.fonts.display, weight: 800 }),
        rect(ctx, m, ruleY, 1 - 2 * m, 0.004, "$ink", { name: "rule" }),
        textLayer(ctx, { role: "date", text: c.date, x: m, y: dateY, w: 1 - 2 * m, h: dateH, size: 0.2, font: ctx.fonts.display, weight: 800, leading: 1, fill: true, color: c.headline ? "$ink" : "$accent" }),
        textLayer(ctx, { role: "venue", text: joinLines(c.venue, c.where), x: m, y: infoY, w: col, h: infoH * 0.78, size: 0.04, weight: 600 }),
        textLayer(ctx, { role: "time", text: joinLines(c.time, c.price, c.support), x: m + col + 0.04, y: infoY, w: col, h: infoH * 0.78, size: 0.038 }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: m, y: infoY + infoH * 0.8, w: 1 - 2 * m, h: infoH * 0.2, size: 0.028, color: "$accent", weight: 600, valign: "bottom" }),
      ]),
    };
  },
};

const punk: Recipe = {
  id: "punk",
  name: "Xerox Punk",
  tagline: "Photocopied, pasted, taped",
  description:
    "Late-70s handbill: 1-bit photocopy photo, slightly crooked paste-up, tape strips, condensed caps and typewriter details.",
  palettes: [
    { paper: "#F2EFE6", ink: "#0D0D0D", accent: "#F7E733", accent2: "#E8457C" },
    { paper: "#F7E733", ink: "#0D0D0D", accent: "#FFFFFF", accent2: "#E8457C" },
    { paper: "#F27BAA", ink: "#0D0D0D", accent: "#F2EFE6", accent2: "#F7E733" },
  ],
  fontPairs: [
    { display: "Anton", text: "Special Elite" },
    { display: "Archivo Black", text: "IBM Plex Mono" },
    { display: "Bebas Neue", text: "Special Elite" },
  ],
  treatments: ["threshold", "mono"],
  mirrorable: true,
  build(ctx) {
    const c = copy(ctx);
    const r = (n: number) => (ctx.rng() - 0.5) * n;
    const square = ctx.ar < 1.1;
    const markH = square ? 0.14 : 0.13;
    const pX = 0.07;
    const pW = 0.86;
    const pY = 0.03 + markH + 0.035;
    const pH = Math.min(square ? 0.4 : 0.45, pW / (photoAspect(ctx) * ctx.ar));
    const tilt = -1.5 + r(1);
    const after = pY + pH + 0.04;
    const room = 0.965 - after;
    const dateH = room * 0.38;
    const stripY = after + dateH + room * 0.05;
    const stripH = room * 0.3;
    const timeY = stripY + stripH + room * 0.05;
    const sticker = square ? 0.2 : 0.22;
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "speckle", color: "$ink", opacity: 0.35, scale: 1 },
          { kind: "halftone", color: "$ink", opacity: 0.06, scale: 1.2 },
          { kind: "grain", color: "$ink", opacity: 0.12, scale: 1.4 },
        ],
      },
      layers: compact<Layer>([
        rect(ctx, -0.15, pY + pH * 0.18, 1.3, pH * 0.64, "$accent2", { rotation: -8 + r(2), name: "slash" }),
        ctx.photo && rect(ctx, pX + 0.016, pY + 0.016 / ctx.ar, pW, pH, "$ink", { rotation: tilt, name: "shadow" }),
        photoLayer(ctx, pX, pY, pW, pH, { rotation: tilt }),
        rect(ctx, 0.02, pY - 0.015, 0.2, 0.035, "$accent", { rotation: -32, opacity: 0.85, name: "tape" }),
        rect(ctx, 0.78, pY + pH - 0.025, 0.2, 0.035, "$accent", { rotation: -28, opacity: 0.85, name: "tape" }),
        bandMark(ctx, 0.06, 0.03, 0.88, markH, { rotation: -2.5 + r(1), font: ctx.fonts.display, weight: 400, transform: "upper" }, "left"),
        shape(ctx, "ellipse", 0.74, pY - (sticker * 0.42) / ctx.ar, sticker, sticker / ctx.ar, "$accent", { rotation: 12, name: "sticker" }),
        textLayer(ctx, { role: "kicker", text: c.headline || "Live!", x: 0.765, y: pY - (sticker * 0.42) / ctx.ar + (sticker * 0.3) / ctx.ar, w: sticker * 0.8, h: (sticker * 0.4) / ctx.ar, size: 0.06, font: ctx.fonts.display, align: "center", valign: "middle", transform: "upper", fill: true, rotation: 12 }),
        rect(ctx, 0.04, after, 0.92, dateH, "$ink", { rotation: -2 + r(0.8), name: "date block" }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.08, y: after + dateH * 0.1, w: 0.84, h: dateH * 0.8, size: 0.14, font: ctx.fonts.display, color: "$paper", align: "center", valign: "middle", transform: "upper", fill: true, rotation: -2 }),
        rect(ctx, 0.1, stripY, 0.84, stripH, "$accent", { rotation: 1.5 + r(0.8), name: "venue strip" }),
        textLayer(ctx, { role: "venue", text: c.venue, x: 0.14, y: stripY + stripH * 0.08, w: 0.76, h: stripH * 0.5, size: 0.06, font: ctx.fonts.display, align: "center", valign: "middle", transform: "upper", fill: true, rotation: 1.5 }),
        c.where && textLayer(ctx, { role: "city", text: c.where, x: 0.14, y: stripY + stripH * 0.6, w: 0.76, h: stripH * 0.3, size: 0.034, align: "center", valign: "middle", rotation: 1.5 }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("  /  "), x: 0.06, y: timeY, w: 0.88, h: Math.max(0.03, 0.965 - timeY - (c.tickets ? 0.035 : 0)), size: 0.036, align: "center", valign: "middle", rotation: -1 }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.08, y: pY + pH + 0.005, w: 0.84, h: 0.03, size: 0.026, transform: "upper", align: "left" }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: 0.06, y: 0.955, w: 0.88, h: 0.03, size: 0.024, align: "center" }),
      ]),
    };
  },
};

const screenprint: Recipe = {
  id: "screenprint",
  name: "Two-Colour Screenprint",
  tagline: "Spot inks, overprint, slight misregistration",
  description:
    "Gig-poster screenprint: duotone photo over a flat colour shape that breaks out behind it, condensed headline, visible misregistration.",
  palettes: [
    { paper: "#EFE6D2", ink: "#1F2A44", accent: "#E4572E", accent2: "#F3A712" },
    { paper: "#F1E9DA", ink: "#3B1F2B", accent: "#2A9D8F", accent2: "#E9C46A" },
    { paper: "#E8E4D8", ink: "#202020", accent: "#C8102E", accent2: "#F2B5A0" },
  ],
  fontPairs: [
    { display: "Bebas Neue", text: "Work Sans" },
    { display: "Oswald", text: "Work Sans" },
    { display: "Alfa Slab One", text: "Oswald" },
  ],
  treatments: ["duotone", "mono"],
  mirrorable: true,
  build(ctx) {
    const c = copy(ctx);
    const p = frame(ctx, 0.08, 0.1, 0.84, ctx.ar < 1.1 ? 0.46 : 0.5);
    const top = p.y + p.h;
    const bottom = 0.955;
    const R = bottom - top;
    const bandY = top + R * 0.05;
    const bandH = R * 0.38;
    const ruleY = bandY + bandH + R * 0.03;
    const infoY = ruleY + R * 0.05;
    const infoH = bottom - infoY - (c.tickets ? 0.035 : 0);
    const circle = 0.78;
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "paper", color: "$ink", opacity: 0.25, scale: 1 },
          { kind: "grain", color: "$ink", opacity: 0.1, scale: 1 },
        ],
      },
      layers: compact<Layer>([
        // The sun sits behind the photo and breaks out at the top right; the photo itself stays unmixed so faces read.
        shape(ctx, "ellipse", 0.3, 0.02, circle, circle / ctx.ar, "$accent", { name: "sun" }),
        photoLayer(ctx, p.x, p.y, p.w, p.h, {
          treatment: treatmentFor(ctx.treatment, "$ink", "#FFFFFF"),
          misregister: { dx: 0.006, dy: 0.004, color: "$accent2" },
        }),
        bandMark(ctx, 0.08, bandY, 0.84, bandH, { font: ctx.fonts.display, weight: 400, transform: "upper" }),
        rect(ctx, 0.08, ruleY, 0.84, 0.006, "$accent", { name: "rule" }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.08, y: infoY, w: 0.46, h: infoH * 0.7, size: 0.2, font: ctx.fonts.display, color: "$accent", transform: "upper", leading: 0.95, fill: true }),
        textLayer(ctx, { role: "venue", text: joinLines(c.venue, c.where), x: 0.57, y: infoY, w: 0.35, h: infoH * 0.64, size: 0.04, weight: 600, align: "right", transform: "upper" }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join(" · "), x: 0.57, y: infoY + infoH * 0.68, w: 0.35, h: infoH * 0.32, size: 0.036, align: "right" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.08, y: infoY + infoH * 0.74, w: 0.46, h: infoH * 0.26, size: 0.03, weight: 600, transform: "upper" }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: 0.08, y: 0.955, w: 0.84, h: 0.03, size: 0.024, color: "$ink" }),
      ]),
    };
  },
};

const letterpress: Recipe = {
  id: "letterpress",
  name: "Letterpress Show Print",
  tagline: "Stacked wood type, two inks, rules",
  description:
    "Hatch Show Print–style: every line fills the measure, two inks on warm stock, horizontal rules and bands divide the information.",
  palettes: [
    { paper: "#E9D9BC", ink: "#1B1B1B", accent: "#C1272D", accent2: "#1B1B1B" },
    { paper: "#F3EAD7", ink: "#1D2B53", accent: "#D9480F", accent2: "#1D2B53" },
    { paper: "#F0E6CF", ink: "#222222", accent: "#2B6E4F", accent2: "#222222" },
  ],
  fontPairs: [
    { display: "Alfa Slab One", text: "Oswald" },
    { display: "Rye", text: "Oswald" },
    { display: "Abril Fatface", text: "Libre Franklin" },
  ],
  treatments: ["tint", "mono", "original"],
  mirrorable: false,
  variants: [
    { id: "photo", label: "Photo cut into the stack" },
    { id: "type", label: "All wood type, no photo" },
  ],
  build(ctx) {
    const c = copy(ctx);
    const m = 0.07;
    const hasPhoto = !!ctx.photo && ctx.variant !== "type";
    let y = 0.035;
    const layers: (Layer | null | false | "")[] = [];
    layers.push(rect(ctx, m, y, 1 - 2 * m, 0.065, "$accent", { name: "top band" }));
    layers.push(
      textLayer(ctx, {
        role: "kicker",
        text: c.headline || (c.city ? `Live in ${c.city}` : "Live"),
        x: m + 0.02,
        y: y + 0.008,
        w: 1 - 2 * m - 0.04,
        h: 0.05,
        size: 0.05,
        font: ctx.fonts.text,
        weight: 600,
        color: "$paper",
        align: "center",
        valign: "middle",
        transform: "upper",
        tracking: 0.12,
      }),
    );
    y += 0.085;
    if (hasPhoto) {
      const p = frame(ctx, m + 0.08, y, 1 - 2 * m - 0.16, ctx.ar < 1.1 ? 0.26 : 0.3);
      layers.push(photoLayer(ctx, p.x, p.y, p.w, p.h, { treatment: treatmentFor(ctx.treatment, "$ink", "$paper") }));
      y += p.h + 0.02;
    }
    const bandH = hasPhoto ? 0.15 : 0.22;
    layers.push(bandMark(ctx, m, y, 1 - 2 * m, bandH, { font: ctx.fonts.display, weight: 400, transform: "upper", align: "center", valign: "middle" }, "center"));
    y += bandH + 0.012;
    layers.push(rect(ctx, m, y, 1 - 2 * m, 0.006, "$accent", { name: "rule" }));
    y += 0.016;
    if (c.support) {
      layers.push(textLayer(ctx, { role: "support", text: c.support, x: m, y, w: 1 - 2 * m, h: 0.04, size: 0.036, font: ctx.fonts.text, weight: 600, align: "center", transform: "upper", tracking: 0.05 }));
      y += 0.05;
    }
    const tail = 0.012 + 0.045 + 0.045 + (c.tickets ? 0.035 : 0);
    const remaining = 0.96 - y - tail;
    const dateH = remaining * 0.56;
    layers.push(textLayer(ctx, { role: "date", text: c.date, x: m, y, w: 1 - 2 * m, h: dateH, size: 0.2, font: ctx.fonts.display, color: "$accent", align: "center", valign: "middle", transform: "upper", fill: true }));
    y += dateH + 0.008;
    const venueH = remaining * 0.4;
    layers.push(textLayer(ctx, { role: "venue", text: c.venue, x: m + 0.05, y, w: 1 - 2 * m - 0.1, h: venueH, size: 0.2, font: ctx.fonts.display, align: "center", valign: "middle", transform: "upper", fill: true }));
    y += venueH + 0.008;
    layers.push(rect(ctx, m, y, 1 - 2 * m, 0.003, "$ink", { name: "rule" }));
    y += 0.012;
    if (c.where) layers.push(textLayer(ctx, { role: "city", text: c.where, x: m, y, w: 1 - 2 * m, h: 0.04, size: 0.032, font: ctx.fonts.text, weight: 600, align: "center", valign: "middle", transform: "upper", tracking: 0.04 }));
    y += 0.045;
    layers.push(textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("  ·  "), x: m, y, w: 1 - 2 * m, h: 0.04, size: 0.032, font: ctx.fonts.text, weight: 600, align: "center", valign: "middle", transform: "upper", tracking: 0.04, color: "$accent" }));
    y += 0.045;
    if (c.tickets) layers.push(textLayer(ctx, { role: "tickets", text: c.tickets, x: m, y, w: 1 - 2 * m, h: 0.03, size: 0.024, font: ctx.fonts.text, align: "center" }));
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "paper", color: "$ink", opacity: 0.35, scale: 1.2 },
          { kind: "speckle", color: "$ink", opacity: 0.15, scale: 1 },
        ],
      },
      layers: compact<Layer>(layers),
    };
  },
};

const bluenote: Recipe = {
  id: "bluenote",
  name: "Blue Note",
  tagline: "Bold crop, one-colour photo, big scale jumps",
  description:
    "Reid Miles–era jazz sleeve: a full-bleed tinted photo, a huge date set against small info, thick accent bars, generous negative space.",
  palettes: [
    { paper: "#F2EFE8", ink: "#121212", accent: "#1E5AA8", accent2: "#E9B824" },
    { paper: "#141414", ink: "#F2EFE8", accent: "#D2691E", accent2: "#8FB8DE" },
    { paper: "#E9E4D8", ink: "#1A1A1A", accent: "#2F7D5B", accent2: "#D94F30" },
  ],
  fontPairs: [
    { display: "Work Sans", text: "Work Sans" },
    { display: "Archivo Black", text: "Inter" },
    { display: "Libre Franklin", text: "Libre Franklin" },
  ],
  treatments: ["tint", "mono", "duotone"],
  mirrorable: true,
  variants: [
    { id: "top", label: "Photo on top, type below" },
    { id: "bottom", label: "Type on top, photo at the foot" },
  ],
  build(ctx) {
    const c = copy(ctx);
    const below = ctx.variant !== "bottom";
    const p = frame(ctx, 0, 0, 1, 0.6, "left");
    const photoY = below ? 0 : 1 - p.h;
    const free = 1 - p.h;
    const markH = Math.min(0.2, Math.max(0.13, free * 0.36));
    const gap = 0.025;
    const pad = 0.05;
    // Stack inside the free area: mark, bar, info. With the photo at the foot, the info comes first.
    const areaY = below ? p.h + gap : pad;
    const areaH = free - gap - pad;
    const markY = below ? areaY : areaY + areaH - markH;
    const infoY = below ? areaY + markH + 0.04 : areaY;
    const infoH = areaH - markH - 0.04;
    const barY = below ? infoY - 0.022 : infoY + infoH + 0.01;
    const textBand = !ctx.logo && below;
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.06, scale: 1 }] },
      layers: compact<Layer>([
        photoLayer(ctx, p.x, photoY, p.w, p.h, { treatment: treatmentFor(ctx.treatment, "$accent", "$paper") }),
        // A typeset name may break out of the frame; a logo always sits on clear paper.
        bandMark(ctx, 0.05, textBand ? p.h - 0.075 : markY, 0.9, textBand ? 0.16 : markH, { font: ctx.fonts.display, weight: 800, transform: "lower", tracking: -0.03, leading: 0.85 }),
        rect(ctx, 0.06, barY, 0.22, 0.012, "$accent2", { name: "accent bar" }),
        c.headline && textLayer(ctx, { role: "kicker", text: c.headline, x: 0.32, y: barY - 0.01, w: 0.62, h: 0.032, size: 0.03, weight: 600, valign: "middle" }),
        textLayer(ctx, { role: "date", text: c.date.toLowerCase(), x: 0.06, y: infoY, w: 0.88, h: infoH * 0.44, size: 0.2, font: ctx.fonts.display, weight: 800, color: "$accent", fill: true, leading: 1, tracking: -0.03 }),
        textLayer(ctx, { role: "venue", text: joinLines(c.venue, c.where), x: 0.06, y: infoY + infoH * 0.5, w: 0.5, h: infoH * 0.5, size: 0.038, weight: 600 }),
        textLayer(ctx, { role: "time", text: joinLines(c.time, c.price, c.support, c.tickets), x: 0.6, y: infoY + infoH * 0.5, w: 0.34, h: infoH * 0.5, size: 0.034, align: "right" }),
      ]),
    };
  },
};

const riso: Recipe = {
  id: "riso",
  name: "Risograph Overprint",
  tagline: "Fluoro inks, multiply, grain",
  description:
    "Zine-style riso: fluoro shapes overprinting behind a grainy one-ink photo, grotesk headline with mono details.",
  palettes: [
    { paper: "#F7F4EE", ink: "#0078BF", accent: "#FF48B0", accent2: "#FFE800" },
    { paper: "#F7F4EE", ink: "#3D5588", accent: "#FF6C2F", accent2: "#00A95C" },
    { paper: "#FFFDF5", ink: "#765BA7", accent: "#FF48B0", accent2: "#00838A" },
  ],
  fontPairs: [
    { display: "Space Grotesk", text: "IBM Plex Mono" },
    { display: "Rubik Mono One", text: "IBM Plex Mono" },
    { display: "Archivo Black", text: "Space Grotesk" },
  ],
  treatments: ["mono", "duotone"],
  mirrorable: true,
  build(ctx) {
    const c = copy(ctx);
    const p = frame(ctx, 0.1, 0.13, 0.8, ctx.ar < 1.1 ? 0.46 : 0.5);
    const top = p.y + p.h;
    const bottom = 0.955;
    const R = bottom - top;
    const bandY = top + R * 0.07;
    const bandH = R * 0.31;
    const dateY = bandY + bandH + R * 0.04;
    const dateH = R * 0.18;
    const infoY = dateY + dateH + R * 0.04;
    const infoH = bottom - infoY;
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "grain", color: "$ink", opacity: 0.12, scale: 1 },
          { kind: "grain", color: "$accent", opacity: 0.08, scale: 1.6 },
        ],
      },
      layers: compact<Layer>([
        shape(ctx, "ellipse", 0.42, 0.03, 0.56, 0.56 / ctx.ar, "$accent", { blend: "multiply" }),
        shape(ctx, "stripes", 0.04, 0.025, 0.5, Math.min(0.2, p.y + p.h * 0.4), "$accent2", { blend: "multiply", rays: 12 }),
        photoLayer(ctx, p.x, p.y, p.w, p.h, { treatment: treatmentFor(ctx.treatment, "$ink", "#FFFFFF") }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.1, y: top + 0.006, w: 0.8, h: R * 0.07, size: 0.028, font: ctx.fonts.text, weight: 700 }),
        bandMark(ctx, 0.06, bandY, 0.88, bandH, { font: ctx.fonts.display, weight: 700, tracking: -0.02, misregister: { dx: 0.004, dy: 0.003, color: "$accent" } }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.06, y: dateY, w: 0.88, h: dateH, size: 0.1, font: ctx.fonts.display, weight: 700, transform: "upper", fill: true, misregister: { dx: 0.003, dy: 0.002, color: "$accent" } }),
        textLayer(ctx, { role: "venue", text: joinLines(c.venue, c.where), x: 0.06, y: infoY, w: 0.52, h: infoH, size: 0.038, font: ctx.fonts.text, weight: 700 }),
        textLayer(ctx, { role: "time", text: joinLines(c.time, c.price, c.tickets), x: 0.6, y: infoY, w: 0.34, h: infoH, size: 0.036, font: ctx.fonts.text, weight: 700, align: "right" }),
      ]),
    };
  },
};

const psych: Recipe = {
  id: "psych",
  name: "Fillmore '67",
  tagline: "Radial, complementary flat inks",
  description:
    "Sixties ballroom poster, restrained: flat complementary inks, a sunburst, the photo framed in a circle, rounded display type. No airbrush glow.",
  palettes: [
    { paper: "#F6E7C8", ink: "#3A1C5C", accent: "#F26B1D", accent2: "#E3B505" },
    { paper: "#FBE3D6", ink: "#0F4C5C", accent: "#E36414", accent2: "#F2A65A" },
    { paper: "#F1E4C3", ink: "#5B1A18", accent: "#3E8A73", accent2: "#E2A33B" },
  ],
  fontPairs: [
    { display: "Shrikhand", text: "Oswald" },
    { display: "Abril Fatface", text: "Work Sans" },
    { display: "Rubik Mono One", text: "Oswald" },
  ],
  treatments: ["duotone", "tint"],
  mirrorable: false,
  build(ctx) {
    const c = copy(ctx);
    const d = ctx.ar < 1.1 ? 0.56 : 0.66;
    const pX = (1 - d) / 2;
    const pY = 0.06;
    const pHy = d / ctx.ar;
    const cx = 0.5;
    const cy = pY + pHy / 2;
    const bandY = pY + pHy + 0.02;
    const R = 0.96 - bandY;
    const bandH = R * 0.3;
    const dateY = bandY + bandH + R * 0.03;
    const dateH = R * 0.2;
    const venueY = dateY + dateH + R * 0.05;
    const treatment = treatmentFor(ctx.treatment, "$ink", "$paper");
    // A circle crops a landscape line-up to its middle, so wide photos sit across the sun as a framed print instead.
    let framed: (Layer | null)[];
    if (photoAspect(ctx) > 1.05) {
      const f = frame(ctx, 0.07, 0, 0.86, pHy);
      const y = cy - f.h / 2;
      const edge = 0.012;
      framed = [
        rect(ctx, f.x - edge, y - edge / ctx.ar, f.w + 2 * edge, f.h + (2 * edge) / ctx.ar, "$ink", { name: "frame" }),
        photoLayer(ctx, f.x, y, f.w, f.h, { treatment }),
      ];
    } else {
      framed = [photoLayer(ctx, pX, pY, d, pHy, { mask: "ellipse", treatment })];
    }
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.1, scale: 1 }] },
      layers: compact<Layer>([
        shape(ctx, "sunburst", cx - 1, cy - 1, 2, 2, "$accent2", { rays: 28, opacity: 0.9 }),
        shape(ctx, "ellipse", pX - 0.03, pY - 0.03 / ctx.ar, d + 0.06, pHy + 0.06 / ctx.ar, "$accent"),
        ...framed,
        bandMark(ctx, 0.07, bandY, 0.86, bandH, { font: ctx.fonts.display, weight: 400, align: "center", valign: "middle" }, "center"),
        rect(ctx, 0, dateY, 1, dateH, "$ink", { name: "date band" }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.08, y: dateY + dateH * 0.12, w: 0.84, h: dateH * 0.76, size: 0.09, font: ctx.fonts.display, color: "$paper", align: "center", valign: "middle", transform: "upper", fill: true }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.where].filter(Boolean).join(" · "), x: 0.06, y: venueY, w: 0.88, h: R * 0.16, size: 0.045, font: ctx.fonts.text, weight: 600, align: "center", valign: "middle", transform: "upper" }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join(" · "), x: 0.08, y: venueY + R * 0.17, w: 0.84, h: R * 0.08, size: 0.036, font: ctx.fonts.text, align: "center", valign: "middle", transform: "upper" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.08, y: venueY + R * 0.25, w: 0.84, h: R * 0.07, size: 0.03, font: ctx.fonts.text, weight: 600, align: "center", transform: "upper" }),
      ]),
    };
  },
};

const tour: Recipe = {
  id: "tour",
  name: "Tour Poster",
  tagline: "Full-bleed photo over a heavy ink panel",
  description:
    "Arena/tour-bill structure: the photo runs edge to edge across the top, a thin accent rule, then a dark panel of huge stacked type: band, date, venue.",
  palettes: [
    { paper: "#111111", ink: "#F4F1EA", accent: "#E8C547", accent2: "#C8372D" },
    { paper: "#1B2A41", ink: "#F2E9DC", accent: "#F28C28", accent2: "#7FB7BE" },
    { paper: "#F4F1EA", ink: "#151515", accent: "#C8372D", accent2: "#151515" },
  ],
  fontPairs: [
    { display: "Bebas Neue", text: "Oswald" },
    { display: "Anton", text: "Work Sans" },
    { display: "Alfa Slab One", text: "Oswald" },
  ],
  treatments: ["mono", "original", "duotone"],
  mirrorable: false,
  variants: [
    { id: "centred", label: "Centred bill" },
    { id: "flush", label: "Flush-left bill" },
  ],
  build(ctx) {
    const c = copy(ctx);
    const p = frame(ctx, 0, 0, 1, ctx.ar < 1.1 ? 0.5 : 0.58);
    const top = p.h;
    const bottom = 0.96;
    const R = bottom - top;
    const flush = ctx.variant === "flush";
    const align = flush ? "left" : "center";
    const x = flush ? 0.11 : 0.07;
    const w = flush ? 0.82 : 0.86;
    const markY = top + R * 0.05;
    const markH = R * 0.3;
    const dateY = markY + markH + R * 0.03;
    const dateH = R * 0.21;
    const venueY = dateY + dateH + R * 0.02;
    const venueH = R * 0.12;
    const lineY = venueY + venueH + R * 0.02;
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.07, scale: 1 }] },
      layers: compact<Layer>([
        photoLayer(ctx, p.x, 0, p.w, p.h),
        rect(ctx, 0, top, 1, 0.008, "$accent", { name: "rule" }),
        flush && rect(ctx, 0.07, dateY, 0.014, lineY + R * 0.13 - dateY, "$accent", { name: "bar" }),
        c.headline && textLayer(ctx, { role: "kicker", text: c.headline, x, y: top + R * 0.015, w, h: R * 0.05, size: 0.03, color: "$accent", align, valign: "middle", transform: "upper", tracking: 0.12, weight: 600 }),
        bandMark(ctx, x, markY, w, markH, { font: ctx.fonts.display, weight: 400, transform: "upper", valign: "middle", color: "$ink" }, align, "$paper"),
        textLayer(ctx, { role: "date", text: c.date, x, y: dateY, w, h: dateH, size: 0.2, font: ctx.fonts.display, color: "$accent", align, valign: "middle", transform: "upper", fill: true }),
        textLayer(ctx, { role: "venue", text: c.venue, x, y: venueY, w, h: venueH, size: 0.2, font: ctx.fonts.display, align, valign: "middle", transform: "upper", fill: true }),
        textLayer(ctx, { role: "city", text: c.where, x, y: lineY, w, h: R * 0.065, size: 0.036, align, valign: "middle", transform: "upper", tracking: 0.04 }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("  ·  "), x, y: lineY + R * 0.065, w, h: R * 0.065, size: 0.036, align, valign: "middle", transform: "upper", tracking: 0.04, color: "$accent" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x, y: lineY + R * 0.13, w, h: R * 0.06, size: 0.03, align, valign: "middle", weight: 600 }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x, y: bottom - 0.03, w, h: 0.03, size: 0.024, align }),
      ]),
    };
  },
};

const split: Recipe = {
  id: "split",
  name: "Split Field",
  tagline: "A solid colour column against the photo",
  description:
    "Modernist split: one full-height column of flat colour carries the date stacked large; the photo, name and venue sit on the open side. Strongly asymmetric.",
  palettes: [
    { paper: "#F3EFE6", ink: "#1A1A1A", accent: "#C8372D", accent2: "#1A1A1A" },
    { paper: "#EDE8DD", ink: "#1E2A3A", accent: "#1E4D8C", accent2: "#E8B54A" },
    { paper: "#F6F0E4", ink: "#2A2118", accent: "#2F6B4F", accent2: "#D98E2B" },
  ],
  fontPairs: [
    { display: "Archivo Black", text: "Inter" },
    { display: "Oswald", text: "Work Sans" },
    { display: "Abril Fatface", text: "Libre Franklin" },
  ],
  treatments: ["mono", "original", "duotone"],
  mirrorable: true,
  build(ctx) {
    const c = copy(ctx);
    const colW = 0.34;
    const x = colW + 0.05;
    const w = 1 - x - 0.05;
    const mY = 0.05 / ctx.ar;
    const p = frame(ctx, x, mY, w, ctx.ar < 1.1 ? 0.42 : 0.36, "left");
    const top = p.y + p.h;
    const bottom = 1 - mY;
    const R = bottom - top;
    const markY = top + R * 0.05;
    const markH = R * 0.36;
    const venueY = markY + markH + R * 0.05;
    const [dow, mon, num] = c.date.split(" ");
    const stacked = num ? `${dow}\n${mon}\n${num}` : c.date;
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.07, scale: 1 }] },
      layers: compact<Layer>([
        rect(ctx, 0, 0, colW, 1, "$accent", { name: "column" }),
        textLayer(ctx, { role: "date", text: stacked, x: 0.05, y: mY + 0.01, w: colW - 0.1, h: 0.5, size: 0.2, font: ctx.fonts.display, color: "$paper", transform: "upper", fill: true, leading: 0.95 }),
        rect(ctx, 0.05, 0.56, 0.1, 0.008, "$paper", { name: "rule" }),
        textLayer(ctx, { role: "time", text: joinLines(c.time, c.price), x: 0.05, y: 0.59, w: colW - 0.08, h: 0.2, size: 0.042, color: "$paper", weight: 600 }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: 0.05, y: bottom - 0.08, w: colW - 0.09, h: 0.08, size: 0.024, color: "$paper", valign: "bottom" }),
        photoLayer(ctx, p.x, p.y, p.w, p.h),
        bandMark(ctx, x, markY, w, markH, { font: ctx.fonts.display, weight: 800, valign: "middle" }, "left"),
        textLayer(ctx, { role: "venue", text: c.venue, x, y: venueY, w, h: R * 0.2, size: 0.2, font: ctx.fonts.display, transform: "upper", fill: true, valign: "bottom" }),
        textLayer(ctx, { role: "city", text: c.where, x, y: venueY + R * 0.22, w, h: R * 0.14, size: 0.038 }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x, y: venueY + R * 0.38, w, h: R * 0.1, size: 0.034, weight: 600 }),
        c.headline && textLayer(ctx, { role: "kicker", text: c.headline, x, y: top + 0.008, w, h: R * 0.05, size: 0.026, weight: 600, color: "$accent", transform: "upper", tracking: 0.08 }),
      ]),
    };
  },
};

const bigtype: Recipe = {
  id: "bigtype",
  name: "Big Type",
  tagline: "The date is the picture",
  description:
    "Type-led bill: the date set enormous across the top, the venue as a second headline, and the photo as a small print in the corner next to the logo.",
  palettes: [
    { paper: "#F4EFE4", ink: "#141414", accent: "#E2402B", accent2: "#141414" },
    { paper: "#141414", ink: "#F4EFE4", accent: "#F5C518", accent2: "#F4EFE4" },
    { paper: "#E9F0EC", ink: "#0E3B2E", accent: "#0E3B2E", accent2: "#E2402B" },
  ],
  fontPairs: [
    { display: "Anton", text: "Inter" },
    { display: "Bebas Neue", text: "Work Sans" },
    { display: "Archivo Black", text: "Space Grotesk" },
  ],
  treatments: ["mono", "original", "threshold"],
  mirrorable: true,
  build(ctx) {
    const c = copy(ctx);
    const m = 0.06;
    const [dow, mon, num] = c.date.split(" ");
    const stacked = num ? `${dow} ${mon}\n${num}` : c.date;
    let y = 0.035;
    const dateH = ctx.ar < 1.1 ? 0.34 : 0.36;
    const dateY = y;
    y += dateH + 0.015;
    const ruleY = y;
    y += 0.02;
    const venueY = y;
    const venueH = ctx.ar < 1.1 ? 0.09 : 0.08;
    y += venueH + 0.01;
    const whereY = y;
    y += 0.045;
    const timeY = y;
    y += 0.045;
    const supportY = y;
    if (c.support) y += 0.04;
    const rowY = y + 0.02;
    const bottom = 0.965;
    const rowH = bottom - rowY;
    const p = frame(ctx, 0.38, rowY, 1 - 0.38 - m, rowH, "right");
    const photoY = bottom - p.h;
    const markH = Math.min(rowH, 0.18);
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.08, scale: 1 }] },
      layers: compact<Layer>([
        textLayer(ctx, { role: "date", text: stacked, x: m, y: dateY, w: 1 - 2 * m, h: dateH, size: 0.3, font: ctx.fonts.display, color: "$accent", transform: "upper", fill: true, leading: 0.9 }),
        rect(ctx, m, ruleY, 1 - 2 * m, 0.006, "$ink", { name: "rule" }),
        textLayer(ctx, { role: "venue", text: c.venue, x: m, y: venueY, w: 1 - 2 * m, h: venueH, size: 0.2, font: ctx.fonts.display, transform: "upper", fill: true }),
        textLayer(ctx, { role: "city", text: c.where, x: m, y: whereY, w: 1 - 2 * m, h: 0.04, size: 0.038, weight: 600 }),
        textLayer(ctx, { role: "time", text: [c.time, c.price, c.tickets].filter(Boolean).join("  ·  "), x: m, y: timeY, w: 1 - 2 * m, h: 0.04, size: 0.038 }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: m, y: supportY, w: 1 - 2 * m, h: 0.035, size: 0.03, weight: 600 }),
        photoLayer(ctx, p.x, photoY, p.w, p.h),
        bandMark(ctx, m, bottom - markH, 0.3, markH, { font: ctx.fonts.display, weight: 800, valign: "bottom" }, "left"),
        c.headline && textLayer(ctx, { role: "kicker", text: c.headline, x: m, y: bottom - markH - 0.04, w: 0.3, h: 0.035, size: 0.026, weight: 600, transform: "upper" }),
      ]),
    };
  },
};

const ticket: Recipe = {
  id: "ticket",
  name: "Admit One",
  tagline: "The flyer is the ticket",
  description:
    "An old theatre ticket blown up to poster size: cream stock on a coloured ground, notched corners at the stub, a perforation line, slab and mono type, a serial number.",
  palettes: [
    { paper: "#B3261E", ink: "#1E1E1E", accent: "#F3E9D2", accent2: "#B3261E" },
    { paper: "#2A6F97", ink: "#14213D", accent: "#FBF3E4", accent2: "#2A6F97" },
    { paper: "#1F6F50", ink: "#2B2B2B", accent: "#F1E7D0", accent2: "#1F6F50" },
  ],
  fontPairs: [
    { display: "Alfa Slab One", text: "IBM Plex Mono" },
    { display: "Rye", text: "Oswald" },
    { display: "Oswald", text: "IBM Plex Mono" },
  ],
  treatments: ["mono", "tint", "duotone"],
  mirrorable: false,
  build(ctx) {
    const c = copy(ctx);
    const tx = 0.06;
    const ty = 0.035;
    const tw = 0.88;
    const th = 0.93;
    const stubY = ty + th * 0.8;
    const notch = 0.09;
    const ix = tx + 0.06;
    const iw = tw - 0.12;
    let y = ty + 0.025;
    const kickY = y;
    y += 0.045;
    const p = frame(ctx, ix, y, iw, ctx.ar < 1.1 ? 0.3 : 0.32);
    y += p.h + 0.02;
    const room = stubY - 0.02 - y;
    const markY = y;
    const markH = room * 0.38;
    const dateY = markY + markH + room * 0.02;
    const dateH = room * 0.28;
    const venueY = dateY + dateH + room * 0.02;
    const venueH = room * 0.17;
    const whereY = venueY + venueH + room * 0.01;
    const serial = `No. ${String(100000 + Math.floor(ctx.rng() * 900000))}`;
    const stubH = ty + th - stubY;
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.1, scale: 1 }] },
      layers: compact<Layer>([
        rect(ctx, tx, ty, tw, th, "$accent", { name: "ticket" }),
        shape(ctx, "ellipse", tx - notch / 2, stubY - notch / 2 / ctx.ar, notch, notch / ctx.ar, "$paper", { name: "notch" }),
        shape(ctx, "ellipse", tx + tw - notch / 2, stubY - notch / 2 / ctx.ar, notch, notch / ctx.ar, "$paper", { name: "notch" }),
        // Horizontal bars, turned on their side, read as a perforated tear line across the ticket.
        shape(ctx, "stripes", 0.5 - 0.003, stubY - (tw - notch) / 2 / ctx.ar, 0.006, (tw - notch) / ctx.ar, "$ink", { rotation: 90, rays: 30, opacity: 0.55, name: "perforation" }),
        textLayer(ctx, { role: "kicker", text: c.headline || "Admit one", x: ix, y: kickY, w: iw, h: 0.035, size: 0.034, font: ctx.fonts.text, weight: 600, color: "$accent2", align: "center", valign: "middle", transform: "upper", tracking: 0.3 }),
        photoLayer(ctx, p.x, p.y, p.w, p.h, { treatment: treatmentFor(ctx.treatment, "$ink", "$accent") }),
        bandMark(ctx, ix, markY, iw, markH, { font: ctx.fonts.display, weight: 400, transform: "upper", valign: "middle" }, "center", "$accent"),
        textLayer(ctx, { role: "date", text: c.date, x: ix, y: dateY, w: iw, h: dateH, size: 0.2, font: ctx.fonts.display, color: "$accent2", align: "center", valign: "middle", transform: "upper", fill: true }),
        textLayer(ctx, { role: "venue", text: c.venue, x: ix + 0.04, y: venueY, w: iw - 0.08, h: venueH, size: 0.2, font: ctx.fonts.display, align: "center", valign: "middle", transform: "upper", fill: true }),
        textLayer(ctx, { role: "city", text: c.where, x: ix, y: whereY, w: iw, h: room * 0.1, size: 0.032, align: "center", valign: "middle" }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("  ·  "), x: ix, y: stubY + stubH * 0.18, w: iw, h: stubH * 0.32, size: 0.036, weight: 600, align: "center", valign: "middle", transform: "upper" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: ix, y: stubY + stubH * 0.5, w: iw, h: stubH * 0.2, size: 0.028, align: "center", valign: "middle" }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: ix, y: stubY + stubH * 0.68, w: iw * 0.68, h: stubH * 0.22, size: 0.024, valign: "middle" }),
        textLayer(ctx, { role: "custom", text: serial, x: ix + iw * 0.68, y: stubY + stubH * 0.68, w: iw * 0.32, h: stubH * 0.22, size: 0.024, color: "$accent2", align: "right", valign: "middle" }),
      ]),
    };
  },
};

export const RECIPES: Recipe[] = [swiss, punk, screenprint, letterpress, bluenote, riso, psych, tour, split, bigtype, ticket, ...BILL_RECIPES];
/** Includes the custom bill, which only appears when an art director has written a line stack for it. */
export const RECIPE_MAP: Record<string, Recipe> = Object.fromEntries([...RECIPES, CUSTOM_BILL].map((r) => [r.id, r]));

export function mirrorLayers(layers: Layer[]): Layer[] {
  return layers.map((l) => {
    const flipped = { ...l, x: 1 - l.x - l.w, rotation: -l.rotation } as Layer;
    if (flipped.type === "text" || flipped.type === "logo") {
      flipped.align = flipped.align === "left" ? "right" : flipped.align === "right" ? "left" : "center";
    }
    if (flipped.type === "photo" || flipped.type === "text") {
      if (flipped.misregister) flipped.misregister = { ...flipped.misregister, dx: -flipped.misregister.dx };
    }
    return flipped;
  });
}

/**
 * Band photos are line-ups: people stand across the full width, heads near the top. A frame narrower than the
 * photo (or a zoom, or a curved top) would crop the outer members, so such frames are reshaped to the photo's
 * own proportions. The bottom edge stays put because recipes hang names and accents off it.
 */
export function keepWholeLineup(layers: Layer[], photo: AssetRef | null, ar: number): Layer[] {
  if (!photo || photo.width <= 0 || photo.height <= 0) return layers;
  const aspect = photo.width / photo.height;
  return layers.map((l) => {
    if (l.type !== "photo" || l.assetId !== photo.id) return l;
    const cropsSides = aspect > (l.w / (l.h * ar)) * 1.01 || l.zoom > 1;
    const curvedTop = (l.mask === "arch" || l.mask === "ellipse") && aspect > 1.05;
    if (!cropsSides && !curvedTop) return l;
    const h = Math.min(l.h, l.w / (aspect * ar));
    return { ...l, y: l.y + (l.h - h), h, zoom: 1, mask: curvedTop ? "rect" : l.mask };
  });
}

export function buildSpec(recipeId: string, input: BuildInput): FlyerSpec {
  const recipe = RECIPE_MAP[recipeId] ?? swiss;
  const seed = input.seed ?? Math.floor(Math.random() * 1e9);
  const rng = mulberry32(seed);
  const palette = input.palette ?? recipe.palettes[(input.paletteIndex ?? 0) % recipe.palettes.length];
  const fonts = input.fonts ?? recipe.fontPairs[(input.fontIndex ?? 0) % recipe.fontPairs.length];
  const treatment = input.treatment && recipe.treatments.includes(input.treatment) ? input.treatment : input.treatment ?? recipe.treatments[0];
  const variant = recipe.variants?.some((v) => v.id === input.variant) ? input.variant! : (recipe.variants?.[0]?.id ?? "");
  const f = FORMATS[input.format];
  let n = 0;
  const ctx: Ctx = {
    brief: input.brief,
    band: input.bandName || "Your Band",
    ar: f.h / f.w,
    palette,
    fonts,
    photo: input.photo,
    logo: input.logo,
    treatment,
    variant,
    bill: input.bill,
    rng,
    id: (p) => `${p}-${++n}`,
  };
  const built = recipe.build(ctx);
  const fitted = keepWholeLineup(built.layers, input.photo, ctx.ar);
  const layers = input.mirror && recipe.mirrorable ? mirrorLayers(fitted) : fitted;
  return {
    version: 1,
    format: input.format,
    recipeId: recipe.id,
    ...(variant ? { variant } : {}),
    ...(built.bill ? { bill: built.bill } : {}),
    seed,
    palette,
    fonts,
    background: built.background,
    layers: layers.filter((l) => !(l.type === "text" && !l.text.trim())),
  };
}
