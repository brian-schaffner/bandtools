import type { Brief, FlyerSpec, FormatId, Layer, Palette, PhotoLayer, ShapeLayer, TextLayer, Treatment } from "./spec.ts";

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
  variant?: string;
  bill?: unknown;
}

export interface RecipeVariant {
  id: string;
  label: string;
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
  /** Structural alternatives of the same tradition; the first is the default. */
  variants?: RecipeVariant[];
  build: (ctx: Ctx) => Pick<FlyerSpec, "background" | "layers"> & { bill?: unknown };
  /** Built from a line stack; extra copy (songs, tagline, banner) is set as type. */
  bill?: boolean;
}

export interface Ctx {
  brief: Brief;
  band: string;
  ar: number; // height / width
  palette: Palette;
  fonts: { display: string; text: string };
  photo: AssetRef | null;
  logo: AssetRef | null;
  treatment: Treatment["mode"];
  variant: string;
  /** A line stack supplied by the art director (bill recipes only). */
  bill?: unknown;
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

// ---------- colour helpers ----------

export function hexLum(hex: string): number {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return 0.5;
  const n = parseInt(m[1], 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function tok(ctx: Ctx, c: string): string {
  return c.startsWith("$") ? (ctx.palette[c.slice(1) as keyof Palette] ?? ctx.palette.ink) : c;
}

export const isDark = (ctx: Ctx, c: string) => hexLum(tok(ctx, c)) < 0.2;

/** Whichever of paper and ink is lighter; white if both are dark. */
export function lightInk(ctx: Ctx): string {
  const best = hexLum(ctx.palette.paper) >= hexLum(ctx.palette.ink) ? "$paper" : "$ink";
  return isDark(ctx, best) ? "#FFFFFF" : best;
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

export const words = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\b(the|band)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/**
 * Calendar titles are usually "Venue presents Band" or just the venue, which only repeats what the logo and venue
 * line already say. Those are dropped; a real headline ("Halloween Bash") is kept.
 */
export function usefulHeadline(headline: string, band: string, venue: string): string {
  const h = words(headline);
  if (!h) return "";
  const b = words(band);
  const v = words(venue);
  if ((b && h.includes(b)) || (v && h.includes(v))) return "";
  if (/\b(presents?|live at|live in|featuring|feat)\b/.test(h)) return "";
  return headline.trim();
}

const presenterFrom = (headline: string) => {
  const m = /^(.{2,60}?)\s+presents?\b/i.exec(headline.trim());
  return m ? `${m[1]} presents` : "";
};

/** "Venue presents Band" names a presenter, unless the presenter is the venue already set on its own line. */
const derivedPresenter = (headline: string, venue: string) => {
  const p = presenterFrom(headline);
  return p && words(p.replace(/\s+presents?$/i, "")) !== words(venue) ? p : "";
};

const songList = (songs: string[] | undefined) =>
  (songs ?? [])
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 6);

export function copy(ctx: Ctx) {
  const brief = ctx.brief;
  const show = brief.showTime && brief.endTime ? `Show ${brief.showTime} – ${brief.endTime}` : brief.showTime ? `Show ${brief.showTime}` : brief.endTime ? `Until ${brief.endTime}` : "";
  const time = [brief.doors && `Doors ${brief.doors}`, show].filter(Boolean).join(" · ");
  return {
    headline: usefulHeadline(brief.headline, ctx.band, brief.venue),
    date: formatDate(brief.date),
    time,
    venue: brief.venue,
    city: brief.city,
    // A street address usually ends with the city, so it replaces the city wherever a venue line is set.
    where: brief.address || brief.city,
    price: [brief.price, brief.ages].filter(Boolean).join(" · "),
    support: brief.support.filter(Boolean).length ? `with ${brief.support.filter(Boolean).join(" · ")}` : "",
    tickets: brief.tickets,
    extra: brief.extra,
    presenter: brief.presenter?.trim() || derivedPresenter(brief.headline, brief.venue),
    tagline: brief.tagline?.trim() ?? "",
    banner: brief.banner?.trim() ?? "",
    songs: songList(brief.songs),
  };
}

// ---------- layer helpers ----------

export function textLayer(ctx: Ctx, p: Partial<TextLayer> & Pick<TextLayer, "role" | "text" | "x" | "y" | "w" | "h" | "size">): TextLayer {
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
    outline: null,
    inline: null,
    shadow: null,
    arc: 0,
    ...p,
  };
}

export function rect(ctx: Ctx, x: number, y: number, w: number, h: number, fill: string, extra: Partial<Layer> = {}): Layer {
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

export function shape(ctx: Ctx, s: Exclude<ShapeLayer["shape"], "rect">, x: number, y: number, w: number, h: number, fill: string, extra: Partial<Layer> = {}): Layer {
  return { ...(rect(ctx, x, y, w, h, fill) as object), shape: s, name: s, ...extra } as Layer;
}

export function treatmentFor(mode: Treatment["mode"], dark = "$ink", light = "$paper"): Treatment {
  return { mode, dark, light, mid: "$accent", contrast: mode === "threshold" ? 0.1 : 0.15, brightness: 0, threshold: 0.5 };
}

/**
 * A colour mapping whose "light" end is dark (a dark palette's paper) turns faces into silhouettes, so the light end
 * is moved to the palette's lightest ink and the ends are swapped if they arrive reversed.
 */
export function legible(ctx: Ctx, t: Treatment): Treatment {
  if (t.mode === "original" || t.mode === "mono") return t;
  let { dark, light } = t;
  if (hexLum(tok(ctx, light)) < 0.35) light = lightInk(ctx);
  if (hexLum(tok(ctx, dark)) > hexLum(tok(ctx, light))) [dark, light] = [light, dark];
  return { ...t, dark, light };
}

export function photoAspect(ctx: Ctx) {
  return ctx.photo && ctx.photo.height > 0 ? ctx.photo.width / ctx.photo.height : 1.5;
}

/** A frame with the photo's own proportions, as wide as `w` allows without exceeding `maxH`. */
export function frame(ctx: Ctx, x: number, y: number, w: number, maxH: number, align: "left" | "center" | "right" = "center") {
  const aspect = photoAspect(ctx);
  let fw = w;
  let fh = fw / (aspect * ctx.ar);
  if (fh > maxH) {
    fh = maxH;
    fw = fh * aspect * ctx.ar;
  }
  const fx = align === "left" ? x : align === "right" ? x + w - fw : x + (w - fw) / 2;
  return { x: fx, y, w: fw, h: fh };
}

export function photoLayer(ctx: Ctx, x: number, y: number, w: number, h: number, extra: Partial<PhotoLayer> = {}): Layer | null {
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
    cutout: false,
    sticker: null,
    misregister: null,
    rotation: 0,
    opacity: 1,
    blend: "normal",
    hidden: false,
    ...extra,
    treatment: legible(ctx, extra.treatment ?? treatmentFor(ctx.treatment)),
  };
}

/**
 * Band name: the uploaded logo if there is one, otherwise set in the display face. `on` is the colour the mark sits
 * on; a logo on a dark ground is recoloured to the palette's light ink so a black wordmark doesn't vanish.
 */
export function bandMark(ctx: Ctx, x: number, y: number, w: number, h: number, textExtra: Partial<TextLayer> = {}, align: "left" | "center" | "right" = "left", on = "$paper"): Layer {
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
      recolor: isDark(ctx, on) ? lightInk(ctx) : null,
      recolorMode: "tone",
      align,
      backdrop: "auto",
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

export function compact<T>(arr: (T | null | false | undefined | "")[]): T[] {
  return arr.filter(Boolean) as T[];
}

export const joinLines = (...parts: string[]) => parts.filter(Boolean).join("\n");

