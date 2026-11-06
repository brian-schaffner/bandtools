import type { Brief, FlyerSpec, FormatId, Layer, Palette, PhotoLayer, TextLayer, Treatment } from "./spec";
import { FORMATS } from "./spec";

export interface AssetRef {
  id: string;
  width: number;
  height: number;
}

export interface BuildInput {
  brief: Brief;
  bandName: string;
  format: FormatId;
  photo: AssetRef | null;
  logo: AssetRef | null;
  palette?: Palette;
  fonts?: { display: string; text: string };
  treatment?: Treatment["mode"];
  mirror?: boolean;
  seed?: number;
  paletteIndex?: number;
  fontIndex?: number;
}

export interface Recipe {
  id: string;
  name: string;
  tagline: string;
  description: string;
  palettes: Palette[];
  fontPairs: { display: string; text: string }[];
  treatments: Treatment["mode"][];
  mirrorable: boolean;
  build: (ctx: Ctx) => Pick<FlyerSpec, "background" | "layers">;
}

interface Ctx {
  brief: Brief;
  band: string;
  ar: number; // height / width
  palette: Palette;
  fonts: { display: string; text: string };
  photo: AssetRef | null;
  logo: AssetRef | null;
  treatment: Treatment["mode"];
  rng: () => number;
  id: (prefix: string) => string;
}

export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- copy helpers ----------

export function formatDate(raw: string): string {
  if (!raw) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw.trim());
  if (!m) return raw;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  const day = d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
  const mon = d.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
  return `${day} ${mon} ${d.getUTCDate()}`;
}

function copy(brief: Brief) {
  const time = [brief.doors && `Doors ${brief.doors}`, brief.showTime && `Show ${brief.showTime}`]
    .filter(Boolean)
    .join(" · ");
  return {
    date: formatDate(brief.date),
    time,
    venue: brief.venue,
    city: brief.city,
    price: [brief.price, brief.ages].filter(Boolean).join(" · "),
    support: brief.support.filter(Boolean).length ? `with ${brief.support.filter(Boolean).join(" · ")}` : "",
    tickets: brief.tickets,
    extra: brief.extra,
  };
}

// ---------- layer helpers ----------

function textLayer(ctx: Ctx, p: Partial<TextLayer> & Pick<TextLayer, "role" | "text" | "x" | "y" | "w" | "h" | "size">): TextLayer {
  return {
    id: ctx.id("text"),
    name: p.role,
    type: "text",
    font: ctx.fonts.text,
    weight: 400,
    color: "$ink",
    align: "left",
    valign: "top",
    transform: "none",
    tracking: 0,
    leading: 1.1,
    fill: false,
    rotation: 0,
    opacity: 1,
    blend: "normal",
    hidden: false,
    misregister: null,
    ...p,
  };
}

function rect(ctx: Ctx, x: number, y: number, w: number, h: number, fill: string, extra: Partial<Layer> = {}): Layer {
  return {
    id: ctx.id("shape"),
    name: "block",
    type: "shape",
    shape: "rect",
    x,
    y,
    w,
    h,
    fill,
    rays: 24,
    rotation: 0,
    opacity: 1,
    blend: "normal",
    hidden: false,
    ...extra,
  } as Layer;
}

function shape(ctx: Ctx, s: "ellipse" | "sunburst" | "stripes" | "ring", x: number, y: number, w: number, h: number, fill: string, extra: Partial<Layer> = {}): Layer {
  return { ...(rect(ctx, x, y, w, h, fill) as object), shape: s, name: s, ...extra } as Layer;
}

function treatmentFor(mode: Treatment["mode"], dark = "$ink", light = "$paper"): Treatment {
  return { mode, dark, light, contrast: mode === "threshold" ? 0.1 : 0.15, brightness: 0, threshold: 0.5 };
}

function photoLayer(ctx: Ctx, x: number, y: number, w: number, h: number, extra: Partial<PhotoLayer> = {}): Layer | null {
  if (!ctx.photo) return null;
  return {
    id: ctx.id("photo"),
    name: "photo",
    type: "photo",
    assetId: ctx.photo.id,
    x,
    y,
    w,
    h,
    fit: "cover",
    zoom: 1,
    focusX: 0.5,
    focusY: 0.4,
    mask: "rect",
    treatment: treatmentFor(ctx.treatment),
    misregister: null,
    rotation: 0,
    opacity: 1,
    blend: "normal",
    hidden: false,
    ...extra,
  };
}

/** Band name: the uploaded logo if there is one, otherwise set in the display face. */
function bandMark(ctx: Ctx, x: number, y: number, w: number, h: number, textExtra: Partial<TextLayer> = {}, align: "left" | "center" | "right" = "left"): Layer {
  if (ctx.logo) {
    return {
      id: ctx.id("logo"),
      name: "logo",
      type: "logo",
      assetId: ctx.logo.id,
      x,
      y,
      w,
      h,
      recolor: null,
      recolorMode: "tone",
      align,
      rotation: textExtra.rotation ?? 0,
      opacity: 1,
      blend: "normal",
      hidden: false,
    };
  }
  return textLayer(ctx, {
    role: "band",
    text: ctx.band,
    x,
    y,
    w,
    h,
    size: 0.3,
    font: ctx.fonts.display,
    weight: 800,
    fill: true,
    leading: 0.92,
    align,
    valign: "bottom",
    ...textExtra,
  });
}

function compact<T>(arr: (T | null | false | undefined | "")[]): T[] {
  return arr.filter(Boolean) as T[];
}

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
  build(ctx) {
    const c = copy(ctx.brief);
    const m = 0.06;
    const mY = m / ctx.ar;
    const photoH = ctx.ar < 1.1 ? 0.44 : 0.5;
    const bandY = mY + photoH + 0.025;
    const bandH = ctx.ar < 1.1 ? 0.17 : 0.15;
    const ruleY = bandY + bandH + 0.02;
    const col = (1 - 2 * m - 0.04) / 3;
    const infoY = ruleY + 0.02;
    const small = ctx.ar < 1.1 ? 0.028 : 0.026;
    return {
      background: {
        color: "$paper",
        textures: [{ kind: "grain", color: "$ink", opacity: 0.08, scale: 1 }],
      },
      layers: compact<Layer>([
        photoLayer(ctx, m, mY, 1 - 2 * m, photoH, { treatment: treatmentFor(ctx.treatment) }),
        rect(ctx, 0.6, mY + photoH - 0.07, 0.34, 0.14, "$accent", { name: "accent block", blend: "multiply" }),
        ctx.brief.headline &&
          textLayer(ctx, { role: "kicker", text: ctx.brief.headline, x: 0.62, y: mY + photoH - 0.055, w: 0.3, h: 0.1, size: 0.032, weight: 600, color: "$paper", font: ctx.fonts.text }),
        bandMark(ctx, m, bandY, 1 - 2 * m, bandH, { tracking: -0.02, font: ctx.fonts.display, weight: 800 }),
        rect(ctx, m, ruleY, 1 - 2 * m, 0.003, "$ink", { name: "rule" }),
        textLayer(ctx, { role: "date", text: c.date, x: m, y: infoY, w: col, h: 0.08, size: 0.06, font: ctx.fonts.display, weight: 800, leading: 1, fill: true }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.city].filter(Boolean).join("\n"), x: m + col + 0.02, y: infoY, w: col, h: 0.08, size: small * 1.2, weight: 600 }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("\n"), x: m + 2 * (col + 0.02), y: infoY, w: col, h: 0.08, size: small, weight: 400 }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: m, y: infoY + 0.095, w: 2 * col, h: 0.05, size: small * 1.1, weight: 600 }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: m + 2 * (col + 0.02), y: infoY + 0.095, w: col, h: 0.05, size: small * 0.85, color: "$accent", weight: 600 }),
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
    const c = copy(ctx.brief);
    const r = (n: number) => (ctx.rng() - 0.5) * n;
    const pY = 0.21;
    const pH = ctx.ar < 1.1 ? 0.42 : 0.47;
    const boxY = pY + pH + 0.045;
    const boxH = Math.min(0.95 - boxY, 0.24);
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "speckle", color: "$ink", opacity: 0.35, scale: 1 },
          { kind: "grain", color: "$ink", opacity: 0.12, scale: 1.4 },
        ],
      },
      layers: compact<Layer>([
        bandMark(ctx, 0.06, 0.035, 0.88, 0.15, { rotation: -2.5 + r(1), font: ctx.fonts.display, weight: 400, transform: "upper" }),
        photoLayer(ctx, 0.08, pY, 0.84, pH, { rotation: 1.5 + r(1.5), treatment: treatmentFor(ctx.treatment) }),
        rect(ctx, 0.03, pY - 0.01, 0.2, 0.035, "$accent", { rotation: -32, opacity: 0.85, name: "tape" }),
        rect(ctx, 0.78, pY + pH - 0.03, 0.2, 0.035, "$accent", { rotation: -28, opacity: 0.85, name: "tape" }),
        rect(ctx, 0.05, boxY, 0.9, boxH, "$ink", { rotation: -1 + r(0.8), name: "info box" }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.09, y: boxY + 0.02, w: 0.82, h: boxH * 0.42, size: 0.12, font: ctx.fonts.display, color: "$paper", transform: "upper", fill: true, rotation: -1 }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.city].filter(Boolean).join(" — "), x: 0.09, y: boxY + boxH * 0.5, w: 0.82, h: boxH * 0.2, size: 0.04, color: "$paper", transform: "upper", rotation: -1 }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("  /  "), x: 0.09, y: boxY + boxH * 0.72, w: 0.82, h: boxH * 0.2, size: 0.03, color: "$accent", rotation: -1 }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.08, y: 0.185 - 0.005, w: 0.84, h: 0.03, size: 0.026, transform: "upper", align: "right" }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: 0.06, y: 0.955, w: 0.88, h: 0.03, size: 0.022, align: "right" }),
      ]),
    };
  },
};

const screenprint: Recipe = {
  id: "screenprint",
  name: "Two-Colour Screenprint",
  tagline: "Spot inks, overprint, slight misregistration",
  description:
    "Gig-poster screenprint: duotone photo overprinting a flat colour shape, condensed headline, visible misregistration.",
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
    const c = copy(ctx.brief);
    const circle = 0.92;
    const pH = ctx.ar < 1.1 ? 0.48 : 0.52;
    const bandY = 0.1 + pH + 0.025;
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "paper", color: "$ink", opacity: 0.25, scale: 1 },
          { kind: "grain", color: "$ink", opacity: 0.1, scale: 1 },
        ],
      },
      layers: compact<Layer>([
        shape(ctx, "ellipse", 0.22, 0.04, circle, circle / ctx.ar, "$accent", { name: "sun" }),
        photoLayer(ctx, 0.08, 0.1, 0.84, pH, {
          treatment: { ...treatmentFor(ctx.treatment, "$ink", "#FFFFFF") },
          blend: "multiply",
          misregister: { dx: 0.006, dy: 0.004, color: "$accent2" },
        }),
        bandMark(ctx, 0.08, bandY, 0.84, 0.14, { font: ctx.fonts.display, weight: 400, transform: "upper" }),
        rect(ctx, 0.08, bandY + 0.155, 0.84, 0.006, "$accent", { name: "rule" }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.08, y: bandY + 0.175, w: 0.44, h: 0.075, size: 0.2, font: ctx.fonts.display, color: "$accent", transform: "upper", leading: 0.95, fill: true }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.city].filter(Boolean).join("\n"), x: 0.55, y: bandY + 0.175, w: 0.37, h: 0.07, size: 0.034, weight: 600, align: "right", transform: "upper" }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join(" · "), x: 0.55, y: bandY + 0.245, w: 0.37, h: 0.04, size: 0.024, align: "right" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.08, y: 0.045, w: 0.6, h: 0.04, size: 0.03, weight: 600, transform: "upper" }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: 0.08, y: 0.955, w: 0.84, h: 0.03, size: 0.02, color: "$ink" }),
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
  build(ctx) {
    const c = copy(ctx.brief);
    const m = 0.07;
    const hasPhoto = !!ctx.photo;
    const pH = hasPhoto ? (ctx.ar < 1.1 ? 0.26 : 0.3) : 0;
    let y = 0.035;
    const layers: (Layer | null | false | "")[] = [];
    layers.push(rect(ctx, m, y, 1 - 2 * m, 0.065, "$accent", { name: "top band" }));
    layers.push(
      textLayer(ctx, {
        role: "kicker",
        text: ctx.brief.headline || (c.city ? `Live in ${c.city}` : "Live"),
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
      layers.push(photoLayer(ctx, m + 0.08, y, 1 - 2 * m - 0.16, pH, { treatment: treatmentFor(ctx.treatment, "$ink", "$paper") }));
      y += pH + 0.02;
    }
    const bandH = hasPhoto ? 0.15 : 0.24;
    layers.push(bandMark(ctx, m, y, 1 - 2 * m, bandH, { font: ctx.fonts.display, weight: 400, transform: "upper", align: "center", valign: "middle" }, "center"));
    y += bandH + 0.012;
    layers.push(rect(ctx, m, y, 1 - 2 * m, 0.006, "$accent", { name: "rule" }));
    y += 0.016;
    if (c.support) {
      layers.push(textLayer(ctx, { role: "support", text: c.support, x: m, y, w: 1 - 2 * m, h: 0.04, size: 0.036, font: ctx.fonts.text, weight: 600, align: "center", transform: "upper", tracking: 0.05 }));
      y += 0.05;
    }
    const remaining = 0.94 - y;
    const dateH = remaining * 0.36;
    layers.push(textLayer(ctx, { role: "date", text: c.date, x: m, y, w: 1 - 2 * m, h: dateH, size: 0.2, font: ctx.fonts.display, color: "$accent", align: "center", valign: "middle", transform: "upper", fill: true }));
    y += dateH + 0.008;
    const venueH = remaining * 0.26;
    layers.push(textLayer(ctx, { role: "venue", text: c.venue, x: m + 0.05, y, w: 1 - 2 * m - 0.1, h: venueH, size: 0.2, font: ctx.fonts.display, align: "center", valign: "middle", transform: "upper", fill: true }));
    y += venueH + 0.008;
    layers.push(rect(ctx, m, y, 1 - 2 * m, 0.003, "$ink", { name: "rule" }));
    y += 0.012;
    layers.push(
      textLayer(ctx, {
        role: "time",
        text: [c.city, c.time, c.price].filter(Boolean).join("  ·  "),
        x: m,
        y,
        w: 1 - 2 * m,
        h: 0.04,
        size: 0.03,
        font: ctx.fonts.text,
        weight: 600,
        align: "center",
        transform: "upper",
        tracking: 0.04,
      }),
    );
    y += 0.045;
    if (c.tickets) layers.push(textLayer(ctx, { role: "tickets", text: c.tickets, x: m, y, w: 1 - 2 * m, h: 0.03, size: 0.022, font: ctx.fonts.text, align: "center", color: "$accent" }));
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
    "Reid Miles–era jazz sleeve: a tight, tinted photo crop, a huge lowercase name breaking the frame, generous negative space.",
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
  build(ctx) {
    const c = copy(ctx.brief);
    const pH = ctx.ar < 1.1 ? 0.56 : 0.6;
    const nameY = pH - 0.075;
    const infoY = pH + 0.13;
    const small = 0.028;
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.06, scale: 1 }] },
      layers: compact<Layer>([
        photoLayer(ctx, 0, 0, 1, pH, { zoom: 1.35, treatment: treatmentFor(ctx.treatment, "$accent", "$paper") }),
        ctx.brief.headline && textLayer(ctx, { role: "kicker", text: ctx.brief.headline, x: 0.06, y: nameY - 0.04, w: 0.6, h: 0.035, size: 0.03, weight: 600, color: "$paper" }),
        bandMark(ctx, 0.05, nameY, 0.9, 0.16, { font: ctx.fonts.display, weight: 800, transform: "lower", tracking: -0.03, leading: 0.85 }),
        rect(ctx, 0.06, infoY, 0.07, 0.07 / ctx.ar, "$accent2", { name: "accent square" }),
        textLayer(ctx, { role: "support", text: c.support, x: 0.06, y: infoY + 0.07 / ctx.ar + 0.02, w: 0.42, h: 0.08, size: small, weight: 600 }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.52, y: infoY, w: 0.42, h: 0.06, size: 0.055, font: ctx.fonts.display, weight: 800, align: "right", color: "$accent" }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.city].filter(Boolean).join("\n"), x: 0.52, y: infoY + 0.065, w: 0.42, h: 0.07, size: small, weight: 600, align: "right" }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join("\n"), x: 0.52, y: infoY + 0.14, w: 0.42, h: 0.06, size: small * 0.9, align: "right" }),
        c.tickets && textLayer(ctx, { role: "tickets", text: c.tickets, x: 0.06, y: 0.95, w: 0.88, h: 0.03, size: 0.02, align: "left" }),
      ]),
    };
  },
};

const riso: Recipe = {
  id: "riso",
  name: "Risograph Overprint",
  tagline: "Fluoro inks, multiply, grain",
  description:
    "Zine-style riso: two inks overprinting with multiply, a grainy photo in one ink, grotesk headline with mono details.",
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
    const c = copy(ctx.brief);
    const pH = ctx.ar < 1.1 ? 0.48 : 0.5;
    const bandY = 0.12 + pH + 0.03;
    return {
      background: {
        color: "$paper",
        textures: [
          { kind: "grain", color: "$ink", opacity: 0.12, scale: 1 },
          { kind: "grain", color: "$accent", opacity: 0.08, scale: 1.6 },
        ],
      },
      layers: compact<Layer>([
        shape(ctx, "ellipse", 0.04, 0.06, 0.66, 0.66 / ctx.ar, "$accent", { blend: "multiply" }),
        shape(ctx, "stripes", 0.52, 0.03, 0.44, 0.3, "$accent2", { blend: "multiply", rays: 14 }),
        photoLayer(ctx, 0.12, 0.12, 0.76, pH, { mask: "arch", blend: "multiply", treatment: treatmentFor(ctx.treatment, "$ink", "#FFFFFF") }),
        bandMark(ctx, 0.06, bandY, 0.88, 0.13, { font: ctx.fonts.display, weight: 700, tracking: -0.02, misregister: { dx: 0.004, dy: 0.003, color: "$accent" } }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.06, y: bandY + 0.15, w: 0.5, h: 0.06, size: 0.05, font: ctx.fonts.text, weight: 700, transform: "upper" }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.city].filter(Boolean).join("\n"), x: 0.06, y: bandY + 0.215, w: 0.5, h: 0.07, size: 0.03, font: ctx.fonts.text }),
        textLayer(ctx, { role: "time", text: [c.time, c.price, c.tickets].filter(Boolean).join("\n"), x: 0.58, y: bandY + 0.155, w: 0.36, h: 0.12, size: 0.024, font: ctx.fonts.text, align: "right", color: "$accent", blend: "multiply" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.06, y: 0.04, w: 0.5, h: 0.05, size: 0.028, font: ctx.fonts.text, weight: 700 }),
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
    const c = copy(ctx.brief);
    const d = ctx.ar < 1.1 ? 0.56 : 0.66;
    const pX = (1 - d) / 2;
    const pY = 0.06;
    const pHy = d / ctx.ar;
    const cx = 0.5;
    const cy = pY + pHy / 2;
    const bandY = pY + pHy + 0.02;
    return {
      background: { color: "$paper", textures: [{ kind: "grain", color: "$ink", opacity: 0.1, scale: 1 }] },
      layers: compact<Layer>([
        shape(ctx, "sunburst", cx - 1, cy - 1, 2, 2, "$accent2", { rays: 28, opacity: 0.9 }),
        shape(ctx, "ellipse", pX - 0.03, pY - 0.03 / ctx.ar, d + 0.06, pHy + 0.06 / ctx.ar, "$accent"),
        photoLayer(ctx, pX, pY, d, pHy, { mask: "ellipse", treatment: treatmentFor(ctx.treatment, "$ink", "$paper") }),
        bandMark(ctx, 0.07, bandY, 0.86, 0.14, { font: ctx.fonts.display, weight: 400, align: "center", valign: "middle" }, "center"),
        rect(ctx, 0, bandY + 0.155, 1, 0.075, "$ink", { name: "date band" }),
        textLayer(ctx, { role: "date", text: c.date, x: 0.08, y: bandY + 0.165, w: 0.84, h: 0.055, size: 0.06, font: ctx.fonts.display, color: "$paper", align: "center", valign: "middle", transform: "upper" }),
        textLayer(ctx, { role: "venue", text: [c.venue, c.city].filter(Boolean).join(" · "), x: 0.08, y: bandY + 0.245, w: 0.84, h: 0.045, size: 0.04, font: ctx.fonts.text, weight: 600, align: "center", transform: "upper" }),
        textLayer(ctx, { role: "time", text: [c.time, c.price].filter(Boolean).join(" · "), x: 0.08, y: bandY + 0.29, w: 0.84, h: 0.035, size: 0.026, font: ctx.fonts.text, align: "center", transform: "upper" }),
        c.support && textLayer(ctx, { role: "support", text: c.support, x: 0.08, y: bandY + 0.325, w: 0.84, h: 0.035, size: 0.026, font: ctx.fonts.text, weight: 600, align: "center", transform: "upper" }),
      ]),
    };
  },
};

export const RECIPES: Recipe[] = [swiss, punk, screenprint, letterpress, bluenote, riso, psych];
export const RECIPE_MAP: Record<string, Recipe> = Object.fromEntries(RECIPES.map((r) => [r.id, r]));

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

export function buildSpec(recipeId: string, input: BuildInput): FlyerSpec {
  const recipe = RECIPE_MAP[recipeId] ?? swiss;
  const seed = input.seed ?? Math.floor(Math.random() * 1e9);
  const rng = mulberry32(seed);
  const palette = input.palette ?? recipe.palettes[(input.paletteIndex ?? 0) % recipe.palettes.length];
  const fonts = input.fonts ?? recipe.fontPairs[(input.fontIndex ?? 0) % recipe.fontPairs.length];
  const treatment = input.treatment && recipe.treatments.includes(input.treatment) ? input.treatment : input.treatment ?? recipe.treatments[0];
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
    rng,
    id: (p) => `${p}-${++n}`,
  };
  const built = recipe.build(ctx);
  const layers = input.mirror && recipe.mirrorable ? mirrorLayers(built.layers) : built.layers;
  return {
    version: 1,
    format: input.format,
    recipeId: recipe.id,
    seed,
    palette,
    fonts,
    background: built.background,
    layers: layers.filter((l) => !(l.type === "text" && !l.text.trim())),
  };
}
