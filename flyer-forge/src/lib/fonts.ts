/** Free Google Fonts available to every flyer. Weights listed are the ones we load. */
export const FONTS = {
  "Archivo Black": { weights: [400], kind: "display", note: "Heavy grotesk" },
  Anton: { weights: [400], kind: "display", note: "Condensed poster sans" },
  "Bebas Neue": { weights: [400], kind: "display", note: "Tall condensed caps" },
  Oswald: { weights: [400, 600, 700], kind: "both", note: "Condensed gothic" },
  "Alfa Slab One": { weights: [400], kind: "display", note: "Wood-type slab" },
  Rye: { weights: [400], kind: "display", note: "Ornamented wood type" },
  "Abril Fatface": { weights: [400], kind: "display", note: "Fat face didone" },
  Shrikhand: { weights: [400], kind: "display", note: "Rounded 60s display" },
  "Rubik Mono One": { weights: [400], kind: "display", note: "Wide mono caps" },
  "DM Serif Display": { weights: [400], kind: "display", note: "High-contrast serif" },
  Inter: { weights: [400, 600, 800], kind: "both", note: "Neutral grotesk" },
  "Space Grotesk": { weights: [400, 700], kind: "both", note: "Quirky grotesk" },
  "Work Sans": { weights: [400, 600, 800], kind: "both", note: "Friendly grotesk" },
  "IBM Plex Mono": { weights: [400, 700], kind: "text", note: "Technical mono" },
  "Special Elite": { weights: [400], kind: "text", note: "Typewriter" },
  "Libre Franklin": { weights: [400, 700, 900], kind: "both", note: "American gothic" },
} as const;

export type FontId = keyof typeof FONTS;
export const FONT_IDS = Object.keys(FONTS) as FontId[];

export function googleFontsHref(): string {
  const families = FONT_IDS.map((name) => {
    const weights = FONTS[name].weights;
    const fam = name.replace(/ /g, "+");
    return weights.length === 1 && weights[0] === 400 ? `family=${fam}` : `family=${fam}:wght@${weights.join(";")}`;
  });
  return `https://fonts.googleapis.com/css2?${families.join("&")}&display=block`;
}

export function nearestWeight(font: string, weight: number): number {
  const def = FONTS[font as FontId];
  if (!def) return weight;
  return [...def.weights].sort((a, b) => Math.abs(a - weight) - Math.abs(b - weight))[0];
}

export async function ensureFontsLoaded(specs: { font: string; weight: number }[]): Promise<void> {
  if (typeof document === "undefined") return;
  const unique = new Map<string, string>();
  for (const s of specs) {
    const w = nearestWeight(s.font, s.weight);
    unique.set(`${s.font}-${w}`, `${w} 48px "${s.font}"`);
  }
  await Promise.all([...unique.values()].map((q) => document.fonts.load(q).catch(() => [])));
}
