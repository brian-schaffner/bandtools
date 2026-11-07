import { z } from "zod";

export const FORMATS = {
  "poster-11x17": { label: "Poster · 11×17 in", w: 1100, h: 1700, print: { w: 11, h: 17 } },
  "ig-portrait": { label: "Instagram · 4:5", w: 1080, h: 1350, print: null },
  "ig-square": { label: "Instagram · square", w: 1080, h: 1080, print: null },
  story: { label: "Story · 9:16", w: 1080, h: 1920, print: null },
} as const;
export type FormatId = keyof typeof FORMATS;
export const FORMAT_IDS = Object.keys(FORMATS) as FormatId[];

/** Colours are hex strings or palette tokens ($paper, $ink, $accent, $accent2). */
const color = z.string().min(1);

export const PaletteSchema = z.object({
  paper: z.string(),
  ink: z.string(),
  accent: z.string(),
  accent2: z.string(),
});
export type Palette = z.infer<typeof PaletteSchema>;

export const TextureSchema = z.object({
  kind: z.enum(["grain", "halftone", "paper", "speckle", "lines", "distress"]),
  color,
  opacity: z.number().min(0).max(1),
  scale: z.number().min(0.2).max(6).default(1),
});
export type Texture = z.infer<typeof TextureSchema>;

const base = {
  id: z.string(),
  name: z.string().default(""),
  x: z.number(),
  y: z.number(),
  w: z.number(),
  h: z.number(),
  rotation: z.number().default(0),
  opacity: z.number().min(0).max(1).default(1),
  blend: z.enum(["normal", "multiply", "screen"]).default("normal"),
  hidden: z.boolean().default(false),
};

export const ShapeLayerSchema = z.object({
  ...base,
  type: z.literal("shape"),
  shape: z.enum(["rect", "ellipse", "sunburst", "stripes", "ring", "star", "burst", "ribbon", "frame"]),
  fill: color,
  rays: z.number().int().min(4).max(64).default(24),
});

export const TreatmentSchema = z.object({
  mode: z.enum(["original", "mono", "duotone", "tint", "threshold", "posterize", "halftone"]),
  dark: color.default("$ink"),
  light: color.default("$paper"),
  /** Middle tone for posterize. */
  mid: color.default("$accent"),
  contrast: z.number().min(-1).max(1).default(0),
  brightness: z.number().min(-1).max(1).default(0),
  threshold: z.number().min(0.05).max(0.95).default(0.5),
});
export type Treatment = z.infer<typeof TreatmentSchema>;

export const PhotoLayerSchema = z.object({
  ...base,
  type: z.literal("photo"),
  assetId: z.string().nullable(),
  fit: z.enum(["cover", "contain"]).default("cover"),
  zoom: z.number().min(1).max(4).default(1),
  focusX: z.number().min(0).max(1).default(0.5),
  focusY: z.number().min(0).max(1).default(0.4),
  mask: z.enum(["rect", "ellipse", "arch", "slant"]).default("rect"),
  /** Hide a plain studio background so the people stand on the design. Pixels are untouched; only alpha changes. */
  cutout: z.boolean().default(false),
  /** Outline colour drawn around a cut-out, like a sticker. */
  sticker: color.nullable().default(null),
  treatment: TreatmentSchema,
  misregister: z
    .object({ dx: z.number(), dy: z.number(), color })
    .nullable()
    .default(null),
});

export const LogoLayerSchema = z.object({
  ...base,
  type: z.literal("logo"),
  assetId: z.string().nullable(),
  recolor: color.nullable().default(null),
  /** tone keeps internal logo detail (luminance → colour); solid flattens every opaque pixel to one ink. */
  recolorMode: z.enum(["tone", "solid"]).default("tone"),
  align: z.enum(["left", "center", "right"]).default("center"),
  /** auto turns a flat white box (a logo saved without transparency) transparent; badge sets it in a white circle. */
  backdrop: z.enum(["auto", "keep", "remove", "badge"]).default("auto"),
});

export const TEXT_ROLES = [
  "headline",
  "band",
  "date",
  "time",
  "venue",
  "city",
  "price",
  "support",
  "tickets",
  "kicker",
  "custom",
] as const;
export type TextRole = (typeof TEXT_ROLES)[number];

export const TextLayerSchema = z.object({
  ...base,
  type: z.literal("text"),
  role: z.enum(TEXT_ROLES),
  text: z.string(),
  font: z.string(),
  weight: z.number().default(400),
  size: z.number().min(0.005).max(0.6),
  color,
  align: z.enum(["left", "center", "right"]).default("left"),
  valign: z.enum(["top", "middle", "bottom"]).default("top"),
  transform: z.enum(["upper", "none", "lower"]).default("none"),
  tracking: z.number().min(-0.1).max(0.5).default(0),
  leading: z.number().min(0.7).max(2).default(1.05),
  fill: z.boolean().default(false),
  misregister: z
    .object({ dx: z.number(), dy: z.number(), color })
    .nullable()
    .default(null),
  /** Flat print effects; widths and offsets are fractions of the font size. */
  outline: z.object({ color, width: z.number().min(0).max(0.3) }).nullable().default(null),
  inline: z.object({ color, width: z.number().min(0).max(0.3) }).nullable().default(null),
  shadow: z.object({ color, dx: z.number().min(-0.3).max(0.3), dy: z.number().min(-0.3).max(0.3) }).nullable().default(null),
  /** Curve a single line: positive arches up, negative sags. 1 ≈ a 140° arc. */
  arc: z.number().min(-1).max(1).default(0),
});

export const LayerSchema = z.discriminatedUnion("type", [
  ShapeLayerSchema,
  PhotoLayerSchema,
  LogoLayerSchema,
  TextLayerSchema,
]);
export type Layer = z.infer<typeof LayerSchema>;
export type ShapeLayer = z.infer<typeof ShapeLayerSchema>;
export type PhotoLayer = z.infer<typeof PhotoLayerSchema>;
export type LogoLayer = z.infer<typeof LogoLayerSchema>;
export type TextLayer = z.infer<typeof TextLayerSchema>;

export const SpecSchema = z.object({
  version: z.literal(1).default(1),
  format: z.enum(FORMAT_IDS as [FormatId, ...FormatId[]]),
  recipeId: z.string(),
  variant: z.string().optional(),
  /** The line stack a bill-style layout was built from, kept so it can be re-laid out for another format. */
  bill: z.unknown().optional(),
  seed: z.number().int(),
  palette: PaletteSchema,
  fonts: z.object({ display: z.string(), text: z.string() }),
  background: z.object({ color, textures: z.array(TextureSchema).default([]) }),
  layers: z.array(LayerSchema),
});
export type FlyerSpec = z.infer<typeof SpecSchema>;

export const BriefSchema = z.object({
  headline: z.string().default(""),
  /** "Ernie's Tavern presents" */
  presenter: z.string().default(""),
  /** A short line in the band's voice: "A night of honky-tonk and soul". */
  tagline: z.string().default(""),
  /** A shout line: "In person!", "One night only". */
  banner: z.string().default(""),
  /** Song titles to bill, e.g. from the gig's set list. */
  songs: z.array(z.string()).default([]),
  date: z.string().default(""),
  doors: z.string().default(""),
  showTime: z.string().default(""),
  endTime: z.string().default(""),
  venue: z.string().default(""),
  city: z.string().default(""),
  address: z.string().default(""),
  price: z.string().default(""),
  ages: z.string().default(""),
  support: z.array(z.string()).default([]),
  tickets: z.string().default(""),
  extra: z.string().default(""),
  mood: z.string().default(""),
  format: z.enum(FORMAT_IDS as [FormatId, ...FormatId[]]).default("poster-11x17"),
  photoId: z.string().nullable().default(null),
  logoId: z.string().nullable().default(null),
});
export type Brief = z.infer<typeof BriefSchema>;

export function resolveColor(c: string | null | undefined, palette: Palette): string {
  if (!c) return palette.ink;
  if (c.startsWith("$")) {
    const key = c.slice(1) as keyof Palette;
    return palette[key] ?? palette.ink;
  }
  return c;
}

export function parseSpec(input: unknown): FlyerSpec {
  return SpecSchema.parse(input);
}

export function safeParseSpec(input: unknown) {
  return SpecSchema.safeParse(input);
}
