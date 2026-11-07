import { buildSpec, mirrorLayers, mulberry32, RECIPES, RECIPE_MAP, type AssetRef } from "./recipes";
import type { Brief, FlyerSpec, Layer, Palette, PhotoLayer, TextLayer, Treatment } from "./spec";
import { FONT_IDS, FONTS } from "./fonts";
import type { Asset, Band, ConceptDirection } from "./types";

const MOOD_HINTS: [RegExp, string[]][] = [
  [/jazz|soul|blues|swing|bebop|lounge/i, ["bluenote", "split", "ticket", "letterpress"]],
  [/punk|hardcore|garage|thrash|grunge|noise|diy/i, ["punk", "bigtype", "screenprint", "riso"]],
  [/folk|country|americana|bluegrass|roots|honky|western|rockabilly/i, ["letterpress", "ticket", "screenprint", "bluenote"]],
  [/psych|60s|sixties|funk|groove|stoner|desert/i, ["psych", "screenprint", "riso"]],
  [/electro|synth|dream|shoegaze|pop|dance|zine|indie pop/i, ["riso", "split", "swiss", "screenprint"]],
  [/minimal|modern|post-rock|math|ambient|experimental|clean/i, ["swiss", "split", "bigtype", "bluenote"]],
  [/rock|indie|alt|metal|surf/i, ["tour", "screenprint", "punk", "bigtype"]],
];

export function pickRecipes(text: string, exclude: string[], count: number, seed: number): string[] {
  const rng = mulberry32(seed);
  const scores = new Map(RECIPES.map((r) => [r.id, rng() * 0.5]));
  for (const [re, ids] of MOOD_HINTS) {
    if (re.test(text)) ids.forEach((id, i) => scores.set(id, (scores.get(id) ?? 0) + 3 - i));
  }
  return [...scores.entries()]
    .filter(([id]) => !exclude.includes(id))
    .sort((a, b) => b[1] - a[1])
    .slice(0, count)
    .map(([id]) => id);
}

export function defaultPhoto(photos: Asset[], brief: Brief): Asset | null {
  const usable = photos.filter((p) => !p.archived);
  return (
    usable.find((p) => p.id === brief.photoId) ??
    usable.find((p) => p.isPrimary) ??
    usable.find((p) => p.photoKind === "group") ??
    usable[0] ??
    null
  );
}

export function defaultLogo(logos: Asset[], brief: Brief): Asset | null {
  if (brief.logoId === "none") return null;
  const usable = logos.filter((l) => !l.archived);
  return usable.find((l) => l.id === brief.logoId) ?? usable.find((l) => l.isPrimary) ?? usable[0] ?? null;
}

const AVOID_BY_RECIPE: Record<string, string[]> = {
  swiss: ["Dead-centre symmetry", "Effects on type", "Edge-to-edge detail"],
  punk: ["Cinematic HDR gloss", "Plastic people", "Synthwave palette"],
  screenprint: ["Smoke & lens-flare soup", "Unmotivated gradients", "Fake grunge overlays"],
  letterpress: ["Garbled lettering", "Effects on type", "Info as an afterthought"],
  bluenote: ["Edge-to-edge detail", "Dead-centre symmetry", "Cinematic HDR gloss"],
  riso: ["Synthwave palette", "Glossy sheen", "Fake grunge overlays"],
  psych: ["Airbrushed glow", "Synthwave gradients", "Genre clip-art clichés"],
  tour: ["Smoke & lens-flare soup", "Info as an afterthought", "Glossy sheen"],
  split: ["Dead-centre symmetry", "Edge-to-edge detail", "Unmotivated gradients"],
  bigtype: ["Info as an afterthought", "Effects on type", "Stock-photo hero shot"],
  ticket: ["Genre clip-art clichés", "Fake grunge overlays", "Garbled lettering"],
};

export function mockConcepts(brief: Brief, band: Band, photos: Asset[], logos: Asset[], exclude: string[], count = 3): ConceptDirection[] {
  const seed = Math.floor(Math.random() * 1e9);
  const rng = mulberry32(seed);
  const ids = pickRecipes(`${brief.mood} ${band.genre}`, exclude, count, seed);
  const photo = defaultPhoto(photos, brief);
  const logo = defaultLogo(logos, brief);
  return ids.map((id) => {
    const r = RECIPE_MAP[id];
    const variants = r.variants ?? [];
    return {
      recipeId: id,
      variant: variants.length ? variants[Math.floor(rng() * variants.length)].id : undefined,
      title: r.name,
      rationale: `${r.description} ${brief.mood ? `Chosen to match "${brief.mood}".` : ""}`.trim(),
      paletteIndex: Math.floor(rng() * r.palettes.length),
      fontIndex: Math.floor(rng() * r.fontPairs.length),
      treatment: r.treatments[Math.floor(rng() * r.treatments.length)],
      mirror: r.mirrorable && rng() > 0.5,
      photoId: photo?.id ?? null,
      logoId: logo?.id ?? null,
      avoids: AVOID_BY_RECIPE[id] ?? [],
    };
  });
}

export function assetRef(a: Asset | null | undefined): AssetRef | null {
  return a ? { id: a.id, width: a.width, height: a.height } : null;
}

export function directionToSpec(
  d: ConceptDirection,
  brief: Brief,
  band: Band,
  photos: Asset[],
  logos: Asset[],
  seed?: number,
): FlyerSpec {
  const photo = photos.find((p) => p.id === d.photoId) ?? null;
  const logo = logos.find((l) => l.id === d.logoId) ?? null;
  const spec = buildSpec(d.recipeId, {
    brief,
    bandName: band.name,
    format: brief.format,
    photo: assetRef(photo),
    logo: assetRef(logo),
    palette: d.palette,
    paletteIndex: d.paletteIndex,
    fonts: d.fonts,
    fontIndex: d.fontIndex,
    treatment: d.treatment as Treatment["mode"] | undefined,
    mirror: d.mirror,
    variant: d.variant,
    seed,
  });
  if (photo) {
    for (const l of spec.layers) {
      if (l.type === "photo" && l.assetId === photo.id) {
        l.focusX = photo.focalX;
        l.focusY = photo.focalY;
      }
    }
  }
  return spec;
}

// ---------- evolve ----------

export const LOCKABLE = ["palette", "fonts", "layout", "photo", "treatment", "texture"] as const;
export type Lockable = (typeof LOCKABLE)[number];

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

function otherPalette(spec: FlyerSpec, rng: () => number): Palette {
  const own = RECIPE_MAP[spec.recipeId]?.palettes ?? [];
  const pool = rng() < 0.7 && own.length > 1 ? own : RECIPES.flatMap((r) => r.palettes);
  const options = pool.filter((p) => JSON.stringify(p) !== JSON.stringify(spec.palette));
  return clone(options[Math.floor(rng() * options.length)] ?? spec.palette);
}

function otherFonts(spec: FlyerSpec, rng: () => number) {
  const own = RECIPE_MAP[spec.recipeId]?.fontPairs ?? [];
  const options = own.filter((f) => f.display !== spec.fonts.display || f.text !== spec.fonts.text);
  if (options.length && rng() < 0.75) return options[Math.floor(rng() * options.length)];
  const displays = FONT_IDS.filter((f) => FONTS[f].kind !== "text");
  const texts = FONT_IDS.filter((f) => FONTS[f].kind !== "display");
  return { display: displays[Math.floor(rng() * displays.length)], text: texts[Math.floor(rng() * texts.length)] };
}

export function setFonts(spec: FlyerSpec, fonts: { display: string; text: string }): FlyerSpec {
  const s = clone(spec);
  for (const l of s.layers) {
    if (l.type !== "text") continue;
    if (l.font === spec.fonts.display) l.font = fonts.display;
    else if (l.font === spec.fonts.text) l.font = fonts.text;
  }
  s.fonts = fonts;
  return s;
}

/** A logo recoloured for a dark ground keeps that only while the new paper is still dark. */
function lightLogoInk(p: Palette): string | null {
  const paper = luminanceOf(p.paper);
  const ink = luminanceOf(p.ink);
  if (paper > 0.45) return null;
  return ink > paper ? "$ink" : "#FFFFFF";
}

function luminanceOf(hex: string) {
  const n = parseInt(hex.replace("#", ""), 16);
  if (Number.isNaN(n)) return 0.5;
  return (0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
}

const TREATMENTS: Treatment["mode"][] = ["original", "mono", "duotone", "tint", "threshold"];

function mutate(spec: FlyerSpec, what: Lockable, rng: () => number, photos: Asset[]): { spec: FlyerSpec; label: string } {
  let s = clone(spec);
  switch (what) {
    case "palette":
      s.palette = otherPalette(s, rng);
      s.layers = s.layers.map((l) => (l.type === "logo" && l.recolor?.startsWith("$") ? { ...l, recolor: lightLogoInk(s.palette) } : l));
      return { spec: s, label: "palette" };
    case "fonts":
      return { spec: setFonts(s, otherFonts(s, rng)), label: "type" };
    case "layout": {
      const recipe = RECIPE_MAP[s.recipeId];
      if (recipe?.mirrorable && rng() < 0.5) {
        s.layers = mirrorLayers(s.layers);
        return { spec: s, label: "mirrored layout" };
      }
      const photo = s.layers.find((l): l is PhotoLayer => l.type === "photo");
      if (photo) {
        const masks: PhotoLayer["mask"][] = ["rect", "ellipse", "arch", "slant"];
        if (rng() < 0.4) photo.mask = masks.filter((m) => m !== photo.mask)[Math.floor(rng() * 3)];
        else {
          photo.zoom = Math.min(2.2, Math.max(1, photo.zoom * (0.8 + rng() * 0.7)));
          photo.focusX = Math.min(1, Math.max(0, photo.focusX + (rng() - 0.5) * 0.3));
        }
        return { spec: s, label: "crop & frame" };
      }
      s.layers = mirrorLayers(s.layers);
      return { spec: s, label: "mirrored layout" };
    }
    case "photo": {
      const photoLayers = s.layers.filter((l): l is PhotoLayer => l.type === "photo");
      const usable = photos.filter((p) => !p.archived);
      if (!photoLayers.length || usable.length < 2) return mutate(s, "treatment", rng, photos);
      for (const l of photoLayers) {
        const others = usable.filter((p) => p.id !== l.assetId);
        const next = others[Math.floor(rng() * others.length)];
        l.assetId = next.id;
        l.focusX = next.focalX;
        l.focusY = next.focalY;
      }
      return { spec: s, label: "different photo" };
    }
    case "treatment": {
      const allowed = RECIPE_MAP[s.recipeId]?.treatments ?? TREATMENTS;
      for (const l of s.layers) {
        if (l.type !== "photo") continue;
        const pool = (rng() < 0.7 ? allowed : TREATMENTS).filter((m) => m !== l.treatment.mode);
        l.treatment = { ...l.treatment, mode: pool[Math.floor(rng() * pool.length)] ?? "mono" };
      }
      return { spec: s, label: "photo treatment" };
    }
    case "texture": {
      const kinds = ["grain", "halftone", "paper", "speckle", "lines"] as const;
      if (rng() < 0.5 && s.background.textures.length) {
        s.background.textures = s.background.textures.map((t) => ({ ...t, opacity: Math.min(0.6, Math.max(0.03, t.opacity * (0.5 + rng() * 1.2))) }));
      } else {
        s.background.textures = [
          { kind: kinds[Math.floor(rng() * kinds.length)], color: "$ink", opacity: 0.08 + rng() * 0.2, scale: 0.8 + rng() * 0.8 },
        ];
      }
      s = { ...s };
      return { spec: s, label: "print texture" };
    }
  }
}

export function evolve(spec: FlyerSpec, locks: Lockable[], count: number, photos: Asset[]): { spec: FlyerSpec; label: string }[] {
  const free = LOCKABLE.filter((k) => !locks.includes(k));
  if (!free.length) return [];
  const out: { spec: FlyerSpec; label: string }[] = [];
  const base = Math.floor(Math.random() * 1e9);
  for (let i = 0; i < count; i++) {
    const rng = mulberry32(base + i * 7919);
    const picks = [...free].sort(() => rng() - 0.5).slice(0, Math.min(free.length, 1 + Math.floor(rng() * 2)));
    let s = spec;
    const labels: string[] = [];
    for (const p of picks) {
      const r = mutate(s, p, rng, photos);
      s = r.spec;
      labels.push(r.label);
    }
    out.push({ spec: { ...s, seed: base + i }, label: `Evolved: ${labels.join(" + ")}` });
  }
  return out;
}

// ---------- plain-language edits without AI ----------

const NAMED: Record<string, string> = {
  red: "#C8102E",
  orange: "#E4572E",
  yellow: "#F2C200",
  green: "#2B6E4F",
  teal: "#2A9D8F",
  blue: "#1E5AA8",
  navy: "#1D2B53",
  purple: "#5B3A8C",
  pink: "#E8457C",
  black: "#111111",
  white: "#F7F5F0",
  cream: "#F1E9DA",
  gold: "#D4A017",
};

const ROLE_WORDS: [RegExp, (l: Layer) => boolean][] = [
  [/\b(band|name|title)\b/, (l) => (l.type === "text" && l.role === "band") || l.type === "logo"],
  [/\blogo\b/, (l) => l.type === "logo"],
  [/\bdate\b/, (l) => l.type === "text" && l.role === "date"],
  [/\bvenue\b/, (l) => l.type === "text" && (l.role === "venue" || l.role === "city")],
  [/\b(time|doors)\b/, (l) => l.type === "text" && l.role === "time"],
  [/\b(price|cost)\b/, (l) => l.type === "text" && (l.role === "price" || l.role === "time")],
  [/\b(support|opener|openers)\b/, (l) => l.type === "text" && l.role === "support"],
  [/\b(photo|picture|image)\b/, (l) => l.type === "photo"],
  [/\b(headline|kicker|tour)\b/, (l) => l.type === "text" && (l.role === "kicker" || l.role === "headline")],
];

function scaleLayer(l: Layer, k: number) {
  const cx = l.x + l.w / 2;
  const cy = l.y + l.h / 2;
  const w = Math.min(1.2, l.w * k);
  const h = Math.min(1.2, l.h * k);
  const anchorLeft = l.type === "text" && l.align === "left";
  const anchorRight = l.type === "text" && l.align === "right";
  l.x = anchorLeft ? l.x : anchorRight ? l.x + l.w - w : cx - w / 2;
  l.y = cy - h / 2;
  l.w = w;
  l.h = h;
  if (l.type === "text") l.size = Math.min(0.6, l.size * k);
}

export function localEdit(spec: FlyerSpec, instruction: string, photos: Asset[]): { spec: FlyerSpec; note: string } | null {
  let s = clone(spec);
  const notes: string[] = [];
  const clauses = instruction
    .toLowerCase()
    .replace(/black (and|&|n) white/g, "b&w")
    .split(/\s*(?:,|;|\.\s|\band\b|\bthen\b|\balso\b|\bplus\b)\s*/)
    .filter((c) => c.trim());
  for (const q of clauses) s = editClause(s, q, photos, notes);
  if (!notes.length) return null;
  return { spec: s, note: notes.join(" · ") };
}

function editClause(input: FlyerSpec, q: string, photos: Asset[], notes: string[]): FlyerSpec {
  let s = input;
  const targets = ROLE_WORDS.filter(([re]) => re.test(q)).map(([, f]) => f);
  const pick = (l: Layer) => targets.some((f) => f(l));

  const bigger = /\b(bigger|larger|increase|more prominent|louder|huge)\b/.test(q);
  const smaller = /\b(smaller|reduce|decrease|less prominent|quieter|tiny)\b/.test(q);
  if ((bigger || smaller) && targets.length) {
    const k = bigger ? 1.15 : 0.87;
    s.layers.filter(pick).forEach((l) => scaleLayer(l, k));
    notes.push(`${bigger ? "Enlarged" : "Reduced"} ${s.layers.filter(pick).map((l) => l.name || l.type).join(", ")}`);
  }

  const photoLayers = () => s.layers.filter((l): l is PhotoLayer => l.type === "photo");
  const setMode = (mode: Treatment["mode"], label: string) => {
    photoLayers().forEach((l) => (l.treatment = { ...l.treatment, mode }));
    notes.push(label);
  };
  if (/black and white|b&w|b\/w|\bmono\b|grayscale|greyscale/.test(q)) setMode("mono", "Photo set to black and white");
  else if (/duotone|two.?colou?r/.test(q)) setMode("duotone", "Photo set to duotone");
  else if (/threshold|photocop|xerox|1.?bit/.test(q)) setMode("threshold", "Photo set to photocopy threshold");
  else if (/original colou?r|full colou?r|natural colou?r/.test(q)) setMode("original", "Photo restored to original colour");
  else if (/\btint/.test(q)) setMode("tint", "Photo tinted");

  if (/zoom in|tighter|closer|crop in/.test(q)) {
    photoLayers().forEach((l) => (l.zoom = Math.min(3, l.zoom * 1.25)));
    notes.push("Tighter crop");
  } else if (/zoom out|wider|loosen|crop out|show more/.test(q)) {
    photoLayers().forEach((l) => (l.zoom = Math.max(1, l.zoom / 1.25)));
    notes.push("Wider crop");
  }
  if (/circle|round/.test(q) && /photo|picture|image|frame/.test(q)) {
    photoLayers().forEach((l) => (l.mask = "ellipse"));
    notes.push("Circular photo frame");
  } else if (/\barch/.test(q)) {
    photoLayers().forEach((l) => (l.mask = "arch"));
    notes.push("Arched photo frame");
  } else if (/square|rectang/.test(q) && /photo|frame/.test(q)) {
    photoLayers().forEach((l) => (l.mask = "rect"));
    notes.push("Rectangular photo frame");
  }

  const usable = photos.filter((p) => !p.archived);
  const wantGroup = /group (photo|shot|pic)|whole band|full band/.test(q);
  const wantSolo = /individual|solo|single member/.test(q);
  if (wantGroup || wantSolo || /(swap|change|different|another|other) (photo|picture|image)/.test(q)) {
    const current = photoLayers()[0]?.assetId;
    const pool = usable.filter((p) => p.id !== current && (!wantGroup || p.photoKind === "group") && (!wantSolo || p.photoKind === "individual"));
    if (pool.length) {
      photoLayers().forEach((l) => {
        l.assetId = pool[0].id;
        l.focusX = pool[0].focalX;
        l.focusY = pool[0].focalY;
      });
      notes.push(`Swapped to "${pool[0].name || "another photo"}"`);
    }
  }

  if (/mirror|flip/.test(q)) {
    s.layers = mirrorLayers(s.layers);
    notes.push("Mirrored layout");
  }
  if (/invert|dark background|darker background|reverse/.test(q)) {
    s.palette = { ...s.palette, paper: s.palette.ink, ink: s.palette.paper };
    notes.push("Inverted paper and ink");
  }
  if (/(new|different|change|other|swap) (palette|colou?rs|inks)/.test(q)) {
    s.palette = otherPalette(s, mulberry32(Date.now()));
    notes.push("New palette");
  }
  for (const [name, hex] of Object.entries(NAMED)) {
    const re = new RegExp(`\\b${name}\\b`);
    if (!re.test(q)) continue;
    if (/background|paper|stock/.test(q)) {
      s.palette = { ...s.palette, paper: hex };
      notes.push(`Paper set to ${name}`);
    } else if (/accent|highlight|second/.test(q) || !/ink|text|type/.test(q)) {
      s.palette = { ...s.palette, accent: hex };
      notes.push(`Accent set to ${name}`);
    } else {
      s.palette = { ...s.palette, ink: hex };
      notes.push(`Ink set to ${name}`);
    }
    break;
  }
  if (/(different|new|change|swap|other) (font|type|typeface|fonts)/.test(q)) {
    s = setFonts(s, otherFonts(s, mulberry32(Date.now())));
    notes.push(`Type changed to ${s.fonts.display} / ${s.fonts.text}`);
  }
  if (/(no|remove|less|lose|cut) (the )?(grain|texture|noise)/.test(q)) {
    s.background.textures = /no|remove|lose|cut/.test(q) ? [] : s.background.textures.map((t) => ({ ...t, opacity: t.opacity * 0.5 }));
    notes.push("Reduced print texture");
  } else if (/more (grain|texture|grit)|grittier|rougher/.test(q)) {
    s.background.textures = s.background.textures.length
      ? s.background.textures.map((t) => ({ ...t, opacity: Math.min(0.7, t.opacity * 1.6) }))
      : [{ kind: "grain", color: "$ink", opacity: 0.18, scale: 1 }];
    notes.push("More print texture");
  }
  if (/logo/.test(q) && /(one|single|1).?colou?r|recolou?r|ink colou?r/.test(q)) {
    s.layers.forEach((l) => l.type === "logo" && ((l.recolor = "$ink"), (l.recolorMode = "tone")));
    notes.push("Logo recoloured to ink");
  } else if (/original logo|logo.*original/.test(q)) {
    s.layers.forEach((l) => l.type === "logo" && (l.recolor = null));
    notes.push("Logo restored to original colours");
  }
  if (/upper ?case|all caps|capitals/.test(q)) {
    s.layers.filter((l): l is TextLayer => l.type === "text" && (targets.length ? pick(l) : true)).forEach((l) => (l.transform = "upper"));
    notes.push("Set in capitals");
  } else if (/lower ?case/.test(q)) {
    s.layers.filter((l): l is TextLayer => l.type === "text" && (targets.length ? pick(l) : true)).forEach((l) => (l.transform = "lower"));
    notes.push("Set in lowercase");
  }

  return s;
}

export function adaptFormat(spec: FlyerSpec, format: FlyerSpec["format"], brief: Brief, band: Band, photos: Asset[], logos: Asset[]): FlyerSpec {
  const photoId = spec.layers.find((l) => l.type === "photo")?.assetId ?? null;
  const logoId = (spec.layers.find((l) => l.type === "logo") as Layer & { assetId: string | null } | undefined)?.assetId ?? null;
  const treatment = (spec.layers.find((l) => l.type === "photo") as PhotoLayer | undefined)?.treatment.mode;
  const next = directionToSpec(
    { recipeId: spec.recipeId, variant: spec.variant, title: "", rationale: "", palette: spec.palette, fonts: spec.fonts, photoId: photoId as string | null, logoId, treatment },
    { ...brief, format },
    band,
    photos,
    logos,
    spec.seed,
  );
  next.background.textures = clone(spec.background.textures);
  return next;
}
