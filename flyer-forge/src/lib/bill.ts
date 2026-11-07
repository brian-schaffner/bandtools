import { z } from "zod";
import type { Layer, Palette, TextLayer, Texture, Treatment } from "./spec.ts";
import { FONTS } from "./fonts.ts";
import {
  bandMark,
  compact,
  copy,
  frame,
  hexLum,
  photoAspect,
  photoLayer,
  rect,
  shape,
  textLayer,
  tok,
  treatmentFor,
  type Ctx,
  type Recipe,
} from "./kit.ts";

/**
 * A bill is a poster described as a vertical stack of lines, the way wood-type show bills are set: every line is
 * its own size, face, colour and ornament, and fills the measure. An art director (Claude, or a built-in style)
 * writes the stack; this engine turns it into layers, fits every line and guards contrast.
 */

export const BILL_ROLES = [
  "band",
  "presenter",
  "tagline",
  "banner",
  "date",
  "weekday",
  "monthday",
  "time",
  "venue",
  "where",
  "price",
  "support",
  "songs",
  "tickets",
  "custom",
] as const;
export type BillRole = (typeof BILL_ROLES)[number];

const COLOR = /^(\$(paper|ink|accent|accent2)|#[0-9a-fA-F]{6})$/;
const colorField = (fallback: string) => z.string().regex(COLOR).catch(fallback);

export const BillLineSchema = z.object({
  role: z.enum(BILL_ROLES),
  /** Only for custom lines, and as the fallback wording for banner/tagline. Never facts. */
  text: z.string().max(60).optional().catch(undefined),
  size: z.number().min(0.2).max(4).catch(1),
  font: z.string().catch(""),
  weight: z.number().min(100).max(900).catch(400),
  case: z.enum(["upper", "none", "lower"]).catch("upper"),
  color: colorField("$ink"),
  align: z.enum(["left", "center", "right"]).catch("center"),
  effect: z.enum(["none", "outline", "inline", "shadow", "outline-shadow"]).catch("none"),
  effectColor: z.string().regex(COLOR).optional().catch(undefined),
  arc: z.number().min(-1).max(1).catch(0),
  backing: z.enum(["none", "band", "ribbon"]).catch("none"),
  backingColor: z.string().regex(COLOR).optional().catch(undefined),
  ornament: z.enum(["none", "stars", "rule", "rule-above"]).catch("none"),
  tracking: z.number().min(-0.05).max(0.4).catch(0),
  /** Share of the column the line may use, for lines that should sit narrower than the measure. */
  width: z.number().min(0.3).max(1).catch(1),
});
export type BillLine = z.infer<typeof BillLineSchema>;

export const BillPhotoSchema = z.object({
  /** Index in `lines` the photo sits before (stacked), or the first line it sits beside. */
  at: z.number().int().min(0).max(16).catch(2),
  size: z.number().min(0.5).max(6).catch(3),
  style: z.enum(["rect", "framed", "tilted", "cutout", "cutout-burst", "circle"]).catch("framed"),
  side: z.enum(["none", "left", "right"]).catch("none"),
  span: z.number().int().min(1).max(10).catch(4),
  treatment: z.enum(["original", "mono", "duotone", "tint", "threshold", "posterize", "halftone"]).optional().catch(undefined),
});

export const BillSchema = z.object({
  paper: colorField("$paper"),
  frame: z.enum(["none", "single", "double"]).catch("none"),
  texture: z.enum(["clean", "paper", "worn", "halftone"]).catch("paper"),
  backdrop: z.enum(["none", "sunburst", "burst", "rings"]).catch("none"),
  backdropColor: z.string().regex(COLOR).optional().catch(undefined),
  margin: z.number().min(0.02).max(0.1).catch(0.05),
  photo: BillPhotoSchema.nullable().catch(null),
  lines: z.array(z.unknown()).max(18),
});
export type Bill = Omit<z.infer<typeof BillSchema>, "lines"> & { lines: BillLine[] };

export function parseBill(raw: unknown): Bill | null {
  const outer = BillSchema.safeParse(raw);
  if (!outer.success) return null;
  const lines = outer.data.lines.flatMap((l) => {
    const r = BillLineSchema.safeParse(l);
    return r.success ? [r.data] : [];
  });
  if (lines.length < 2) return null;
  return { ...outer.data, lines };
}

// ---------- colour ----------

const contrast = (a: number, b: number) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

/** The requested ink if it reads on the ground, otherwise whichever palette ink reads best. */
function readable(ctx: Ctx, color: string, ground: string, min = 3): string {
  const g = hexLum(tok(ctx, ground));
  if (contrast(hexLum(tok(ctx, color)), g) >= min) return color;
  const options = ["$ink", "$paper", "$accent", "$accent2", "#FFFFFF", "#111111"];
  return options.reduce((best, c) => (contrast(hexLum(tok(ctx, c)), g) > contrast(hexLum(tok(ctx, best)), g) ? c : best), options[0]);
}

const darker = (ctx: Ctx, a: string, b: string) => (hexLum(tok(ctx, a)) <= hexLum(tok(ctx, b)) ? a : b);
const lighter = (ctx: Ctx, a: string, b: string) => (hexLum(tok(ctx, a)) > hexLum(tok(ctx, b)) ? a : b);

// ---------- copy ----------

const ROLE_TO_TEXT: Record<BillRole, TextLayer["role"]> = {
  band: "band",
  presenter: "kicker",
  tagline: "kicker",
  banner: "kicker",
  date: "date",
  weekday: "date",
  monthday: "date",
  time: "time",
  venue: "venue",
  where: "city",
  price: "price",
  support: "support",
  songs: "custom",
  tickets: "tickets",
  custom: "custom",
};

function longDate(raw: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw.trim());
  if (!m) return { weekday: "", monthday: "" };
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return {
    weekday: d.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" }),
    monthday: `${d.toLocaleDateString("en-US", { month: "long", timeZone: "UTC" })} ${d.getUTCDate()}`,
  };
}

function lineText(ctx: Ctx, line: BillLine): string {
  return (rawText(ctx, line) ?? "").trim();
}

function rawText(ctx: Ctx, line: BillLine): string | undefined {
  const c = copy(ctx);
  const own = (line.text ?? "").replace(/\s+/g, " ").trim();
  switch (line.role) {
    case "band":
      return ctx.band;
    case "presenter":
      return c.presenter;
    case "tagline":
      return c.tagline || own;
    case "banner":
      return c.banner || own;
    case "date":
      return c.date;
    case "weekday":
      return longDate(ctx.brief.date).weekday;
    case "monthday":
      return longDate(ctx.brief.date).monthday;
    case "time":
      return c.time;
    case "venue":
      return c.venue;
    case "where":
      return c.where;
    case "price":
      return c.price;
    case "support":
      return c.support;
    case "songs": {
      const q = (c.songs ?? []).map((s) => `“${s}”`);
      if (q.length <= 2) return q.join("  ·  ");
      const half = Math.ceil(q.length / 2);
      return `${q.slice(0, half).join("  ·  ")}\n${q.slice(half).join("  ·  ")}`;
    }
    case "tickets":
      return c.tickets;
    case "custom":
      return own;
  }
}

// ---------- layout ----------

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

const GAP = 0.007;
const RULE = 0.005;

function fontFor(ctx: Ctx, name: string, fallback: string) {
  return name in FONTS ? name : fallback;
}

/**
 * A big line that is wide-limited (a long band name) sets larger broken over two lines, the way show printers set
 * "LINDSEY LANE / BAND". `w` and `h` are in the same units.
 */
function stackForSize(text: string, w: number, h: number, size: number): string {
  const words = text.split(" ");
  if (size < 1.5 || words.length < 2 || text.includes("\n")) return text;
  const em = 0.55;
  const one = Math.min(w / (text.length * em), h / 1.0);
  let best = text;
  let bestPx = one;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(" ");
    const b = words.slice(i).join(" ");
    const px = Math.min(w / (Math.max(a.length, b.length) * em), h / 1.95);
    if (px > bestPx * 1.12) {
      bestPx = px;
      best = `${a}\n${b}`;
    }
  }
  return best;
}

function lineLayers(ctx: Ctx, line: BillLine, text: string, box: Box, col: Box, ground: string): Layer[] {
  const out: (Layer | null)[] = [];
  let tb = { ...box };
  let under = ground;
  const backing = line.backing === "none" ? null : (line.backingColor ?? "$ink");
  if (backing && line.backing === "band") {
    out.push(rect(ctx, col.x, box.y, col.w, box.h, backing, { name: "bar" }));
    tb = { x: box.x + 0.025, y: box.y + box.h * 0.12, w: box.w - 0.05, h: box.h * 0.76 };
    under = backing;
  } else if (backing) {
    const rw = Math.min(col.w, box.w + 0.06);
    out.push(shape(ctx, "ribbon", box.x + (box.w - rw) / 2, box.y, rw, box.h, backing, { name: "ribbon" }));
    tb = { x: box.x + rw * 0.1 - (rw - box.w) / 2, y: box.y + box.h * 0.14, w: rw * 0.8, h: box.h * 0.72 };
    under = backing;
  }
  if (line.ornament === "stars") {
    const sh = Math.min(tb.h * 0.55, 0.05);
    const sw = sh * ctx.ar;
    const color = readable(ctx, line.color === "$ink" ? "$accent" : "$ink", under, 2);
    out.push(shape(ctx, "star", tb.x, tb.y + (tb.h - sh) / 2, sw, sh, color, { name: "star" }));
    out.push(shape(ctx, "star", tb.x + tb.w - sw, tb.y + (tb.h - sh) / 2, sw, sh, color, { name: "star" }));
    tb = { ...tb, x: tb.x + sw + 0.015, w: tb.w - 2 * (sw + 0.015) };
  }
  const color = readable(ctx, line.color, under);
  if (line.role === "band" && ctx.logo) {
    out.push(bandMark(ctx, tb.x, tb.y, tb.w, tb.h, {}, line.align, under));
  } else {
    const fx = line.effect;
    const second = line.effectColor ?? (hexLum(tok(ctx, color)) > 0.4 ? darker(ctx, "$ink", "$paper") : lighter(ctx, "$accent2", "$ink"));
    const effectInk = contrast(hexLum(tok(ctx, second)), hexLum(tok(ctx, color))) >= 1.6 ? second : readable(ctx, "$ink", color, 2);
    const inset = fx === "none" ? 0 : 0.05;
    const arc = text.includes("\n") ? 0 : line.arc;
    out.push(
      textLayer(ctx, {
        role: ROLE_TO_TEXT[line.role],
        text: arc ? text : stackForSize(text, tb.w, tb.h * ctx.ar, line.size),
        x: tb.x + tb.w * inset * 0.5,
        y: tb.y + tb.h * inset,
        w: tb.w * (1 - inset),
        h: tb.h * (1 - inset * 2),
        size: 0.2,
        font: fontFor(ctx, line.font, line.size >= 1 ? ctx.fonts.display : ctx.fonts.text),
        weight: line.weight,
        color,
        align: line.align,
        valign: "middle",
        transform: line.case,
        tracking: line.tracking,
        leading: 0.95,
        fill: true,
        arc,
        outline: fx === "outline" || fx === "outline-shadow" || fx === "inline" ? { color: effectInk, width: fx === "inline" ? 0.05 : 0.04 } : null,
        inline: fx === "inline" ? { color: under, width: 0.03 } : null,
        shadow: fx === "shadow" || fx === "outline-shadow" ? { color: effectInk, dx: 0.05, dy: 0.05 } : null,
      }),
    );
  }
  const ruleColor = readable(ctx, line.color, ground, 2);
  if (line.ornament === "rule") out.push(rect(ctx, col.x, box.y + box.h + RULE * 0.4, col.w, RULE * 0.6, ruleColor, { name: "rule" }));
  if (line.ornament === "rule-above") out.push(rect(ctx, col.x, box.y - RULE, col.w, RULE * 0.6, ruleColor, { name: "rule" }));
  return compact(out);
}

function photoLayers(ctx: Ctx, bill: Bill, box: Box, ground: string, burstFill = "$accent"): Layer[] {
  const p = bill.photo!;
  const mode = p.treatment ?? ctx.treatment;
  const dark = darker(ctx, "$ink", "$paper");
  const light = lighter(ctx, "$ink", "$paper");
  const treatment: Treatment = treatmentFor(mode as Treatment["mode"], dark, light);
  const out: (Layer | null)[] = [];
  const edge = 0.01;
  switch (p.style) {
    case "framed":
      out.push(rect(ctx, box.x - edge, box.y - edge / ctx.ar, box.w + 2 * edge, box.h + (2 * edge) / ctx.ar, readable(ctx, "$ink", ground, 2), { name: "frame" }));
      out.push(photoLayer(ctx, box.x, box.y, box.w, box.h, { treatment }));
      break;
    case "tilted":
      out.push(rect(ctx, box.x + 0.014, box.y + 0.014 / ctx.ar, box.w, box.h, dark, { rotation: -2, name: "shadow" }));
      out.push(photoLayer(ctx, box.x, box.y, box.w, box.h, { treatment, rotation: -2 }));
      out.push(rect(ctx, box.x - 0.03, box.y - 0.012, 0.16, 0.03, "$accent", { rotation: -30, opacity: 0.85, name: "tape" }));
      out.push(rect(ctx, box.x + box.w - 0.13, box.y + box.h - 0.02, 0.16, 0.03, "$accent", { rotation: -25, opacity: 0.85, name: "tape" }));
      break;
    case "cutout":
      // A cut-out on a dark ground gets a light sticker edge so a dark subject doesn't sink into the paper.
      out.push(photoLayer(ctx, box.x, box.y, box.w, box.h, { treatment, cutout: true, sticker: hexLum(tok(ctx, ground)) < 0.2 ? lighter(ctx, "$ink", "$paper") : null }));
      break;
    case "cutout-burst": {
      const bw = Math.min(1, box.w * 1.3);
      const bh = Math.min(box.h * 1.45, (bw / ctx.ar) * 1.1);
      out.push(shape(ctx, "burst", box.x + (box.w - bw) / 2, box.y + (box.h - bh) / 2, bw, bh, burstFill, { rays: 22, name: "burst" }));
      out.push(photoLayer(ctx, box.x, box.y, box.w, box.h, { treatment, cutout: true, sticker: "#FFFFFF" }));
      break;
    }
    case "circle":
      out.push(shape(ctx, "ellipse", box.x - edge, box.y - edge / ctx.ar, box.w + 2 * edge, box.h + (2 * edge) / ctx.ar, readable(ctx, "$ink", ground, 2), { name: "frame" }));
      out.push(photoLayer(ctx, box.x, box.y, box.w, box.h, { treatment, mask: "ellipse" }));
      break;
    default:
      out.push(photoLayer(ctx, box.x, box.y, box.w, box.h, { treatment }));
  }
  return compact(out);
}

const TEXTURES: Record<Bill["texture"], Texture[]> = {
  clean: [{ kind: "grain", color: "$ink", opacity: 0.06, scale: 1 }],
  paper: [
    { kind: "paper", color: "$ink", opacity: 0.3, scale: 1.1 },
    { kind: "grain", color: "$ink", opacity: 0.08, scale: 1 },
  ],
  worn: [
    { kind: "paper", color: "$ink", opacity: 0.3, scale: 1.1 },
    { kind: "distress", color: "$paper", opacity: 0.5, scale: 1 },
    { kind: "speckle", color: "$ink", opacity: 0.12, scale: 1 },
  ],
  halftone: [
    { kind: "halftone", color: "$ink", opacity: 0.08, scale: 1.1 },
    { kind: "grain", color: "$ink", opacity: 0.08, scale: 1 },
  ],
};

export function layoutBill(ctx: Ctx, bill: Bill): { background: { color: string; textures: Texture[] }; layers: Layer[] } {
  const ground = bill.paper;
  const layers: Layer[] = [];
  const mx = bill.margin;
  const my = mx / ctx.ar;
  let col: Box = { x: mx, y: my, w: 1 - 2 * mx, h: 1 - 2 * my };
  const backdrop = bill.backdropColor ?? "$accent2";

  // Rays stay round the edges; the copy sits on a paper starburst so every line keeps the paper as its ground.
  if (bill.backdrop === "sunburst") {
    layers.push(shape(ctx, "sunburst", -0.5, -0.5, 2, 2, backdrop, { rays: 32, opacity: 0.9 }));
    layers.push(shape(ctx, "burst", -0.25, -0.15, 1.5, 1.3, ground, { rays: 44, name: "panel" }));
  }
  if (bill.backdrop === "burst") layers.push(shape(ctx, "burst", 0.02, 0.1, 0.96, 0.8, backdrop, { rays: 26, opacity: 0.95 }));

  if (bill.frame !== "none") {
    const inset = mx * 0.45;
    const fc = readable(ctx, "$ink", ground, 2);
    layers.push(shape(ctx, "frame", inset, inset / ctx.ar, 1 - 2 * inset, 1 - (2 * inset) / ctx.ar, fc, { rays: bill.frame === "double" ? 2 : 1, name: "frame" }));
    col = { x: col.x + 0.02, y: col.y + 0.02 / ctx.ar, w: col.w - 0.04, h: col.h - 0.04 / ctx.ar };
  }

  const underCopy = layers.length;
  const resolved = bill.lines.map((line, i) => ({ line, i, text: lineText(ctx, line) })).filter((r) => r.text.trim() || (r.line.role === "band" && ctx.logo));
  const planned = ctx.photo && bill.photo ? bill.photo : null;
  // Beside the copy a photo gets under half the measure, which leaves a wide line-up as a sliver; stack those.
  const photo = planned && planned.side !== "none" && photoAspect(ctx) > 1.15 ? { ...planned, side: "none" as const, size: Math.max(planned.size, 2.6) } : planned;
  const side = photo && photo.side !== "none" ? photo : null;
  const stackedPhoto = photo && !side ? photo : null;
  const beside = (i: number) => !!side && i >= side.at && i < side.at + side.span;

  // A logo is contained in its line, so a short wide line leaves it small; give the band line more height.
  if (ctx.logo) {
    const logoAspect = ctx.logo.width / Math.max(1, ctx.logo.height);
    const boost = Math.min(1.8, Math.max(1, 2.2 / logoAspect));
    resolved.forEach((r) => r.line.role === "band" && (r.line = { ...r.line, size: r.line.size * boost }));
  }
  const extras = resolved.reduce((n, r) => n + (r.line.ornament === "rule" || r.line.ornament === "rule-above" ? RULE : 0), 0);
  const items = resolved.length + (stackedPhoto ? 1 : 0);
  const avail = col.h - GAP * (items - 1) - extras;
  const lineShare = resolved.reduce((n, r) => n + r.line.size, 0);

  let photoBox: Box | null = null;
  let unit = avail / Math.max(0.1, lineShare);
  if (stackedPhoto) {
    const total = lineShare + stackedPhoto.size;
    const want = (stackedPhoto.size * avail) / total;
    const pw = stackedPhoto.style === "cutout-burst" ? col.w * 0.78 : stackedPhoto.style === "circle" ? col.w * 0.6 : col.w * 0.94;
    const circle = stackedPhoto.style === "circle" && photoAspect(ctx) <= 1.05;
    const f = circle ? { x: col.x + (col.w - pw) / 2, y: 0, w: pw, h: Math.min(want, pw / ctx.ar) } : frame(ctx, col.x + (col.w - pw) / 2, 0, pw, want);
    photoBox = { ...f, x: circle ? col.x + (col.w - f.h * ctx.ar) / 2 : f.x, w: circle ? f.h * ctx.ar : f.w };
    unit = (avail - photoBox.h) / Math.max(0.1, lineShare);
  }

  const sideW = col.w * 0.42;
  let y = col.y;
  let besideTop = -1;
  let besideBottom = -1;
  resolved.forEach((r, k) => {
    if (stackedPhoto && photoBox && r.i >= stackedPhoto.at && (k === 0 || resolved[k - 1].i < stackedPhoto.at)) {
      photoBox.y = y;
      layers.push(...photoLayers(ctx, { ...bill, photo: stackedPhoto }, photoBox, ground));
      y += photoBox.h + GAP;
    }
    if (r.line.ornament === "rule-above") y += RULE;
    const h = r.line.size * unit;
    const narrow = beside(r.i);
    const cx = narrow ? (side!.side === "left" ? col.x + sideW + 0.02 : col.x) : col.x;
    const cw = narrow ? col.w - sideW - 0.02 : col.w;
    const lw = cw * r.line.width;
    const lx = r.line.align === "left" ? cx : r.line.align === "right" ? cx + cw - lw : cx + (cw - lw) / 2;
    if (narrow) {
      if (besideTop < 0) besideTop = y;
      besideBottom = y + h;
    }
    layers.push(...lineLayers(ctx, r.line, r.text, { x: lx, y, w: lw, h }, { x: cx, y, w: cw, h }, ground));
    y += h + GAP + (r.line.ornament === "rule" ? RULE : 0);
  });
  if (stackedPhoto && photoBox && !resolved.some((r) => r.i >= stackedPhoto.at)) {
    photoBox.y = y;
    layers.push(...photoLayers(ctx, { ...bill, photo: stackedPhoto }, photoBox, ground));
  }
  if (side && besideTop >= 0) {
    const f = frame(ctx, side.side === "left" ? col.x : col.x + col.w - sideW, 0, sideW, besideBottom - besideTop, side.side === "left" ? "left" : "right");
    const box = { ...f, y: besideBottom - f.h };
    const style = side.style === "circle" ? "framed" : side.style;
    layers.splice(underCopy, 0, ...photoLayers(ctx, { ...bill, photo: { ...side, style } }, box, ground));
  }

  if (bill.backdrop === "rings") {
    const pb = photoBox ?? { x: 0.25, y: 0.3, w: 0.5, h: 0.3 };
    const cx = pb.x + pb.w / 2;
    const cy = pb.y + pb.h / 2;
    const rings = [0.18, 0.3, 0.42, 0.54, 0.66].map((r, i) =>
      shape(ctx, "ring", cx - r, cy - r / ctx.ar, 2 * r, (2 * r) / ctx.ar, i % 2 ? backdrop : "$accent", { opacity: 0.85, name: "ring" }),
    );
    layers.unshift(...rings);
  }

  return { background: { color: ground, textures: TEXTURES[bill.texture] }, layers };
}

// ---------- built-in styles ----------

type Style = (ctx: Ctx, pick: <T>(xs: readonly T[]) => T, chance: (p: number) => boolean) => Bill;

const L = (role: BillRole, size: number, p: Partial<BillLine> = {}): BillLine => ({
  role,
  size,
  font: "",
  weight: 400,
  case: "upper",
  color: "$ink",
  align: "center",
  effect: "none",
  arc: 0,
  backing: "none",
  ornament: "none",
  tracking: 0,
  width: 1,
  ...p,
});

/**
 * Moves a show-printer makes between jobs set from the same case: the date and venue blocks trade places, the
 * photo goes above or below the name, a mid-size line is reversed out of a colour band, stars and rules come and go.
 */
function remix(bill: Bill, pick: <T>(xs: readonly T[]) => T, chance: (p: number) => boolean): Bill {
  let lines = bill.lines.map((l) => ({ ...l }));
  const photo = bill.photo ? { ...bill.photo } : null;
  const block = (roles: BillRole[]) => {
    const idx = lines.map((l, i) => (roles.includes(l.role) ? i : -1)).filter((i) => i >= 0);
    return idx.length && idx[idx.length - 1] - idx[0] === idx.length - 1 ? idx : null;
  };
  const when = block(["date", "time"]);
  const where = block(["venue", "where"]);
  if (when && where && chance(0.5)) {
    const [first, second] = when[0] < where[0] ? [when, where] : [where, when];
    if (second[0] === first[first.length - 1] + 1) {
      const a = lines.slice(first[0], first[first.length - 1] + 1);
      const b = lines.slice(second[0], second[second.length - 1] + 1);
      lines = [...lines.slice(0, first[0]), ...b, ...a, ...lines.slice(second[second.length - 1] + 1)];
    }
  }
  const band = lines.findIndex((l) => l.role === "band");
  if (photo && photo.side === "none" && band >= 0 && chance(0.4)) photo.at = photo.at <= band ? band + 1 : band;
  const plain = lines.filter((l, i) => l.backing === "none" && l.size >= 0.8 && l.size <= 1.7 && l.role !== "band" && lines[i - 1]?.backing === "none" && lines[i + 1]?.backing !== "band");
  if (plain.length && chance(0.35)) {
    const l = pick(plain);
    Object.assign(l, { backing: "band", backingColor: pick(["$ink", "$accent"] as const), color: "$paper", effect: "none", arc: 0 });
  }
  if (band >= 0 && lines[band].backing === "none" && !lines[band].arc && chance(0.3)) lines[band].ornament = lines[band].ornament === "stars" ? "none" : "stars";
  const rulable = lines.filter((l) => l.ornament === "none" && l.backing === "none" && l.size >= 0.9 && l.role !== "band");
  if (rulable.length && chance(0.3)) pick(rulable).ornament = "rule";
  return { ...bill, lines, photo, texture: chance(0.25) ? pick(["paper", "worn", "halftone"] as const) : bill.texture };
}

function billRecipe(def: Omit<Recipe, "build" | "mirrorable" | "bill"> & { style: Style }): Recipe {
  return {
    ...def,
    mirrorable: false,
    bill: true,
    build(ctx) {
      const pick = <T,>(xs: readonly T[]) => xs[Math.floor(ctx.rng() * xs.length)];
      const chance = (p: number) => ctx.rng() < p;
      const bill = parseBill(ctx.bill) ?? remix(def.style(ctx, pick, chance), pick, chance);
      return { ...layoutBill(ctx, bill), bill };
    },
  };
}

const SLABS = ["Alfa Slab One", "Ultra", "Bevan", "Holtwood One SC"] as const;
const GOTHICS = ["League Gothic", "Anton", "Bebas Neue", "Oswald"] as const;
const SCRIPTS = ["Lobster", "Yellowtail"] as const;
const WESTERN = ["Sancreek", "Smokum", "Ewert", "Ultra"] as const;

const woodtype = billRecipe({
  id: "woodtype",
  name: "Show Bill",
  tagline: "Wood type stacked to the edges",
  description:
    "Southern show-printer bill (Hatch, Globe, Tribune): every line its own size and face, filling the measure; bold scale jumps between date, venue and band; stars and rules; two or three inks on coloured stock.",
  palettes: [
    { paper: "#F2C230", ink: "#111111", accent: "#B3261E", accent2: "#111111" },
    { paper: "#F1E6CC", ink: "#1A1A1A", accent: "#C1272D", accent2: "#1F5F8B" },
    { paper: "#EE8A2E", ink: "#141414", accent: "#FFF4D6", accent2: "#141414" },
    { paper: "#F3EBD6", ink: "#1E5631", accent: "#111111", accent2: "#C1272D" },
  ],
  fontPairs: [
    { display: "League Gothic", text: "Oswald" },
    { display: "Ultra", text: "Oswald" },
    { display: "Alfa Slab One", text: "Libre Franklin" },
    { display: "Holtwood One SC", text: "Oswald" },
  ],
  treatments: ["mono", "original", "threshold"],
  style: woodtypeStyle,
});

function woodtypeStyle(...[ctx, pick, chance]: Parameters<Style>): Bill {
  {
    const slab = pick(SLABS);
    const gothic = pick(GOTHICS);
    const dateFirst = chance(0.5);
    const dateColor = pick(["$ink", "$accent"]);
    const when = [L("date", 1.7, { font: gothic, color: dateColor, ornament: chance(0.4) ? "rule" : "none" }), L("time", 0.5, { font: ctx.fonts.text, weight: 600 })];
    const where = [L("venue", 1.25, { font: slab }), L("where", 0.42, { font: ctx.fonts.text, weight: 600, tracking: 0.04 })];
    const lines = [
      L("presenter", 0.5, { font: ctx.fonts.text, weight: 600, tracking: 0.08 }),
      ...(dateFirst ? [...when, ...where] : [...where, ...when]),
      L("price", 0.45, { font: ctx.fonts.text, weight: 600, color: "$accent" }),
      L("band", 2.6, { font: ctx.fonts.display, ornament: chance(0.5) ? "stars" : "none", color: pick(["$ink", "$accent"]) }),
      L("support", 0.7, { font: gothic }),
      L("songs", 0.55, { font: ctx.fonts.text, case: "upper", weight: 600 }),
      L("tickets", 0.4, { font: ctx.fonts.text }),
    ];
    const bandAt = lines.findIndex((l) => l.role === "band");
    const sideways = chance(0.3);
    return {
      paper: "$paper",
      frame: "none",
      texture: pick(["worn", "paper"] as const),
      backdrop: "none",
      margin: 0.05,
      photo: sideways
        ? { at: bandAt, size: 3, style: "cutout", side: pick(["left", "right"] as const), span: 3, treatment: undefined }
        : { at: bandAt, size: 3, style: pick(["framed", "rect", "framed"] as const), side: "none", span: 1, treatment: undefined },
      lines,
    };
  }
}

const opry = billRecipe({
  id: "opry",
  name: "Country Show",
  tagline: "Arched title, cut-out star, ribbons",
  description:
    "Opry / barn-dance bill: the venue arched across the top in an ornamented Western face, the performer cut out beside 'starring' and the name, a script shout line, ribbons and a double border on worn stock.",
  palettes: [
    { paper: "#EFE3C8", ink: "#2B3A67", accent: "#B3261E", accent2: "#2B3A67" },
    { paper: "#F4E9D1", ink: "#3B2314", accent: "#C8102E", accent2: "#1D4E89" },
    { paper: "#E9DDC0", ink: "#1F3B2D", accent: "#B5452B", accent2: "#1F3B2D" },
  ],
  fontPairs: [
    { display: "Ultra", text: "Oswald" },
    { display: "Sancreek", text: "Oswald" },
    { display: "Bevan", text: "Libre Franklin" },
  ],
  treatments: ["mono", "tint", "original"],
  style(ctx, pick, chance) {
    const western = pick(WESTERN);
    const script = pick(SCRIPTS);
    const lines = [
      L("presenter", 0.45, { font: ctx.fonts.text, weight: 600, tracking: 0.1 }),
      L("venue", 1.6, { font: western, color: "$accent", arc: chance(0.5) ? 0.5 : 0.35, effect: pick(["shadow", "none", "outline"] as const) }),
      L("custom", 0.38, { text: "Starring", font: script, case: "none", color: "$accent" }),
      L("band", 2.1, { font: ctx.fonts.display }),
      L("banner", 0.65, { text: "Live on stage!", font: script, case: "none", color: "$accent" }),
      L("date", 1.2, { font: pick(GOTHICS), backing: "band", backingColor: "$accent", color: "$paper" }),
      L("time", 0.48, { font: ctx.fonts.text, weight: 600 }),
      L("price", 0.45, { font: ctx.fonts.text, weight: 600 }),
      L("where", 0.5, { font: ctx.fonts.text, weight: 600, backing: "ribbon", backingColor: "$ink", color: "$paper", width: 0.9 }),
      L("tagline", 0.45, { font: script, case: "none" }),
      L("songs", 0.45, { font: ctx.fonts.text, case: "none" }),
    ];
    return {
      paper: "$paper",
      frame: "double",
      texture: "worn",
      backdrop: "none",
      margin: 0.05,
      photo: chance(0.7)
        ? { at: 2, size: 3, style: "cutout", side: pick(["left", "right"] as const), span: 6, treatment: undefined }
        : { at: 2, size: 2.4, style: "framed", side: "none", span: 1, treatment: undefined },
      lines,
    };
  },
});

const inperson = billRecipe({
  id: "inperson",
  name: "In Person",
  tagline: "Shout banner, starburst, huge name",
  description:
    "Fifties R&B package bill: an 'In Person' banner, rays behind a paper starburst, the name in towering condensed caps, song titles in quotes and a script support line on a band.",
  palettes: [
    { paper: "#F4EEDC", ink: "#141414", accent: "#D7261E", accent2: "#D7261E" },
    { paper: "#F3E7C9", ink: "#1C1C1C", accent: "#1E4D8C", accent2: "#1E4D8C" },
    { paper: "#F7EBD0", ink: "#111111", accent: "#2E7D32", accent2: "#2E7D32" },
  ],
  fontPairs: [
    { display: "League Gothic", text: "Oswald" },
    { display: "Anton", text: "Oswald" },
    { display: "Bowlby One SC", text: "Oswald" },
  ],
  treatments: ["mono", "original"],
  style(ctx, pick, chance) {
    const script = pick(SCRIPTS);
    const lines = [
      L("banner", 0.95, { text: "In person", font: pick(["Bowlby One SC", "Anton", "Bungee"] as const), backing: "band", backingColor: "$ink", color: "$paper", tracking: 0.06 }),
      L("tagline", 0.7, { font: script, case: "none", color: "$accent" }),
      L("band", 3, { font: ctx.fonts.display, ornament: "rule" }),
      L("songs", 0.75, { font: pick(GOTHICS) }),
      L("date", 1.1, { font: pick(GOTHICS), color: "$accent" }),
      L("venue", 0.9, { font: pick(SLABS) }),
      L("where", 0.45, { font: ctx.fonts.text, weight: 600 }),
      L("time", 0.45, { font: ctx.fonts.text, weight: 600 }),
      L("support", 0.8, { font: script, case: "none", backing: "band", backingColor: "$ink", color: "$paper" }),
    ];
    return {
      paper: "$paper",
      frame: "none",
      texture: pick(["paper", "worn"] as const),
      backdrop: chance(0.6) ? "sunburst" : "none",
      backdropColor: "$accent2",
      margin: 0.05,
      photo: chance(0.5)
        ? { at: 2, size: 2.4, style: "cutout-burst", side: "none", span: 1, treatment: undefined }
        : { at: 2, size: 3, style: "cutout-burst", side: pick(["left", "right"] as const), span: 2, treatment: undefined },
      lines,
    };
  },
});

const ballroom = billRecipe({
  id: "ballroom",
  name: "Ballroom Psych",
  tagline: "Arched outlined name, rings, boxed venue",
  description:
    "Late-60s ballroom poster: the band name arched in a fat psychedelic face with an outline and offset shadow, concentric rings radiating behind a cut-out photo, the venue boxed at the foot. Flat inks only.",
  palettes: [
    { paper: "#F1E3C6", ink: "#3B1F5C", accent: "#D9381E", accent2: "#F08A24" },
    { paper: "#3A1F12", ink: "#F4C95D", accent: "#E8662A", accent2: "#7A3B1D" },
    { paper: "#F4E6CC", ink: "#1E3D59", accent: "#C0392B", accent2: "#E67E22" },
  ],
  fontPairs: [
    { display: "Kavoon", text: "Oswald" },
    { display: "Chango", text: "Righteous" },
    { display: "Shrikhand", text: "Oswald" },
  ],
  treatments: ["duotone", "posterize", "tint"],
  style(ctx, pick, chance) {
    const lines = [
      L("presenter", 0.45, { font: ctx.fonts.text, tracking: 0.12 }),
      L("band", 2.6, { font: ctx.fonts.display, case: "none", color: "$accent", arc: 0.45, effect: "outline-shadow", effectColor: "$ink" }),
      L("tagline", 0.6, { font: pick(["Righteous", "Kavoon", "Chango"] as const), case: "none" }),
      L("songs", 0.55, { font: ctx.fonts.text }),
      L("venue", 1.3, { font: pick(["Righteous", "Bungee", "Chango"] as const), backing: "band", backingColor: "$ink", color: "$paper" }),
      L("where", 0.45, { font: ctx.fonts.text }),
      L("date", 1.2, { font: ctx.fonts.display, color: "$accent", effect: chance(0.5) ? "shadow" : "none", effectColor: "$ink" }),
      L("time", 0.45, { font: ctx.fonts.text }),
    ];
    return {
      paper: "$paper",
      frame: "none",
      texture: "paper",
      backdrop: "rings",
      backdropColor: "$accent2",
      margin: 0.05,
      photo: { at: 2, size: 3.2, style: "cutout", side: "none", span: 1, treatment: undefined },
      lines,
    };
  },
});

const handbill = billRecipe({
  id: "handbill",
  name: "Punk Handbill",
  tagline: "One-ink photocopy, marker scrawl",
  description:
    "CBGB-era handbill: one ink on black or white, a 1-bit photocopied photo filling the sheet, the name in marker or heavy caps flush left, the date slammed in flush right, scrawled details.",
  palettes: [
    { paper: "#111111", ink: "#F3E58A", accent: "#F3E58A", accent2: "#E8457C" },
    { paper: "#F2EFE6", ink: "#111111", accent: "#E8457C", accent2: "#111111" },
    { paper: "#D7261E", ink: "#111111", accent: "#F2EFE6", accent2: "#111111" },
  ],
  fontPairs: [
    { display: "Permanent Marker", text: "Special Elite" },
    { display: "Bowlby One SC", text: "Special Elite" },
    { display: "Staatliches", text: "IBM Plex Mono" },
  ],
  treatments: ["threshold", "halftone"],
  style(ctx, pick) {
    const lines = [
      L("band", 2.3, { font: ctx.fonts.display, align: "left", width: 0.92 }),
      L("where", 0.5, { font: "Rock Salt", case: "none", align: "left", width: 0.8 }),
      L("tagline", 0.45, { font: ctx.fonts.text, case: "none", align: "left" }),
      L("date", 1.5, { font: pick(["Anton", "Bowlby One SC", "Staatliches"] as const), align: "right", width: 0.85 }),
      L("venue", 0.9, { font: ctx.fonts.display, align: "right", width: 0.85 }),
      L("time", 0.5, { font: ctx.fonts.text, align: "right" }),
      L("support", 0.5, { font: ctx.fonts.text, align: "left" }),
      L("tickets", 0.4, { font: ctx.fonts.text, align: "left" }),
    ];
    return {
      paper: "$paper",
      frame: "none",
      texture: "worn",
      backdrop: "none",
      margin: 0.045,
      photo: { at: 3, size: 3.8, style: pick(["tilted", "rect"] as const), side: "none", span: 1, treatment: undefined },
      lines,
    };
  },
});

const showcard = billRecipe({
  id: "showcard",
  name: "Show Card",
  tagline: "Bordered card, boxed name beside a photo",
  description:
    "Mid-century show card: double border, a 'live from' band across the top, the venue in heavy slab, the name reversed out of an ink box beside a framed photo, starred 'in person' line and the date in a second ink.",
  palettes: [
    { paper: "#F1E7D0", ink: "#1A1A1A", accent: "#C0392B", accent2: "#1A1A1A" },
    { paper: "#EADFC8", ink: "#2A1E17", accent: "#8C2F1C", accent2: "#2A1E17" },
    { paper: "#F4EBD9", ink: "#14213D", accent: "#B23A48", accent2: "#14213D" },
  ],
  fontPairs: [
    { display: "Ultra", text: "Oswald" },
    { display: "Bevan", text: "Oswald" },
    { display: "Graduate", text: "Libre Franklin" },
  ],
  treatments: ["mono", "original", "tint"],
  style(ctx, pick, chance) {
    const lines = [
      L("presenter", 0.6, { font: ctx.fonts.text, weight: 600, backing: "band", backingColor: "$ink", color: "$paper", tracking: 0.08 }),
      L("venue", 1.3, { font: ctx.fonts.display }),
      L("where", 0.5, { font: ctx.fonts.text, weight: 600, ornament: "rule" }),
      L("tagline", 0.5, { font: pick(SCRIPTS), case: "none" }),
      L("band", 2.2, { font: ctx.fonts.display, backing: chance(0.6) ? "band" : "none", backingColor: "$accent", color: "$paper" }),
      L("banner", 0.65, { text: "In person!", font: pick(GOTHICS), ornament: "stars" }),
      L("date", 1.3, { font: ctx.fonts.display, color: "$accent" }),
      L("time", 0.5, { font: ctx.fonts.text, weight: 600 }),
      L("price", 0.45, { font: ctx.fonts.text, weight: 600 }),
      L("tickets", 0.4, { font: ctx.fonts.text }),
    ];
    return {
      paper: "$paper",
      frame: "double",
      texture: pick(["worn", "paper"] as const),
      backdrop: "none",
      margin: 0.05,
      photo: chance(0.55)
        ? { at: 3, size: 3, style: "framed", side: pick(["left", "right"] as const), span: 3, treatment: undefined }
        : { at: 4, size: 2.6, style: "framed", side: "none", span: 1, treatment: undefined },
      lines,
    };
  },
});

/** Claude's own stacks; falls back to a show bill when none was supplied. */
export const CUSTOM_BILL = billRecipe({
  id: "bill",
  name: "Custom Bill",
  tagline: "A line stack designed for this gig",
  description: "A bill whose every line, face, colour, ornament and photo placement was chosen by the art director.",
  palettes: woodtype.palettes,
  fontPairs: woodtype.fontPairs,
  treatments: ["mono", "original", "duotone", "tint", "threshold", "posterize", "halftone"],
  style: woodtypeStyle,
});

export const BILL_RECIPES: Recipe[] = [woodtype, opry, inperson, ballroom, handbill, showcard];

export type { Palette };
