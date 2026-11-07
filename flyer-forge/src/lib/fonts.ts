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
  Ultra: { weights: [400], kind: "display", note: "Fat Clarendon wood type" },
  "Holtwood One SC": { weights: [400], kind: "display", note: "Wide wood-type slab caps" },
  Sancreek: { weights: [400], kind: "display", note: "Western ornamented" },
  Smokum: { weights: [400], kind: "display", note: "Tall Western slab" },
  Ewert: { weights: [400], kind: "display", note: "Victorian decorated wood type" },
  Bevan: { weights: [400], kind: "display", note: "Heavy slab, showcard" },
  Graduate: { weights: [400], kind: "display", note: "College block slab" },
  "Diplomata SC": { weights: [400], kind: "display", note: "Extra-wide circus didone" },
  Fascinate: { weights: [400], kind: "display", note: "Art-deco circus" },
  Chango: { weights: [400], kind: "display", note: "Bubbly 60s fat face" },
  Monoton: { weights: [400], kind: "display", note: "Inline neon 70s" },
  Bungee: { weights: [400], kind: "display", note: "Sign-painter block" },
  "Bungee Shade": { weights: [400], kind: "display", note: "Block with built-in shade" },
  Kavoon: { weights: [400], kind: "display", note: "Psychedelic brush" },
  Righteous: { weights: [400], kind: "display", note: "Rounded 70s geometric" },
  "Permanent Marker": { weights: [400], kind: "display", note: "Felt-tip handwriting" },
  "Rock Salt": { weights: [400], kind: "display", note: "Scrawled handwriting" },
  "Playfair Display": { weights: [400, 700, 900], kind: "both", note: "High-contrast transitional" },
  "Bowlby One SC": { weights: [400], kind: "display", note: "Squat heavy caps" },
  Staatliches: { weights: [400], kind: "display", note: "Square condensed caps" },
  Limelight: { weights: [400], kind: "display", note: "Art-deco theatre" },
  Corben: { weights: [400, 700], kind: "display", note: "Soft Cooper-style" },
  "Pirata One": { weights: [400], kind: "display", note: "Condensed blackletter" },
  "Vast Shadow": { weights: [400], kind: "display", note: "Slab with drop shadow cut in" },
  "League Gothic": { weights: [400], kind: "display", note: "Tall gothic wood type" },
  "Cherry Cream Soda": { weights: [400], kind: "display", note: "50s diner" },
  Lobster: { weights: [400], kind: "display", note: "Script sign-painter" },
  Yellowtail: { weights: [400], kind: "display", note: "50s brush script" },
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
