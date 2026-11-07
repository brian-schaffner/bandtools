import { z } from "zod";
import { aiEnabled, callClaude, extractJson, HARD_RULES, rulebookText } from "@/lib/ai";
import { getBand, jsonError, listAssets, listMembers } from "@/lib/repo";
import { RECIPES, RECIPE_MAP } from "@/lib/recipes";
import { BriefSchema, FORMATS } from "@/lib/spec";
import { FONT_IDS, FONTS } from "@/lib/fonts";
import type { ConceptDirection } from "@/lib/types";
import { consumeQuota, requireViewer } from "@/lib/guard";

const Body = z.object({ brief: BriefSchema, exclude: z.array(z.string()).default([]), count: z.number().int().min(1).max(4).default(3) });
const HEX = /^#[0-9a-fA-F]{6}$/;

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  if (!aiEnabled()) return jsonError("no-key", 503);
  const overQuota = await consumeQuota(viewer, "ai");
  if (overQuota) return overQuota;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid brief");
  const { brief, exclude, count } = parsed.data;
  const [band, members, photos, logos, rules] = await Promise.all([
    getBand(),
    listMembers(),
    listAssets("photo"),
    listAssets("logo"),
    rulebookText(),
  ]);
  const memberName = (id: string) => members.find((m) => m.id === id)?.name ?? "?";
  const usablePhotos = photos.filter((p) => !p.archived);
  const usableLogos = logos.filter((l) => !l.archived);

  const system = `You are the art director for the band "${band.name || "the band"}"${band.genre ? ` (${band.genre})` : ""}${band.hometown ? ` from ${band.hometown}` : ""}.
You choose design directions for gig flyers that look like they were made by a skilled human designer working in a real print tradition, not by an image generator.

${rules}

${HARD_RULES}

You do not draw anything. You pick a layout recipe, palette, font pairing, photo treatment and which of the band's real assets to use. A deterministic layout engine renders it.`;

  const recipeList = RECIPES.filter((r) => !exclude.includes(r.id))
    .map(
      (r) =>
        `- ${r.id}: ${r.name}. ${r.description}\n  palettes: ${r.palettes.map((p, i) => `#${i} paper ${p.paper} ink ${p.ink} accent ${p.accent} accent2 ${p.accent2}`).join(" | ")}\n  font pairs: ${r.fontPairs.map((f, i) => `#${i} ${f.display}/${f.text}`).join(" | ")}\n  treatments: ${r.treatments.join(", ")}${r.variants?.length ? `\n  variants: ${r.variants.map((v) => `${v.id} (${v.label})`).join(" | ")}` : ""}${r.mirrorable ? "\n  mirrorable" : ""}`,
    )
    .join("\n");

  const user = `Gig brief:
${JSON.stringify({ ...brief, format: `${brief.format} (${FORMATS[brief.format].label})` }, null, 2)}

Band photos available (id, type, members, aspect):
${usablePhotos.map((p) => `- ${p.id}: "${p.name}" ${p.photoKind ?? ""} [${p.memberIds.map(memberName).join(", ")}] ${(p.width / p.height).toFixed(2)}:1${p.isPrimary ? " (primary)" : ""}`).join("\n") || "- none uploaded"}

Logos available:
${usableLogos.map((l) => `- ${l.id}: "${l.name}" ${l.mime} ${(l.width / l.height).toFixed(2)}:1${l.isPrimary ? " (primary)" : ""}`).join("\n") || "- none uploaded (band name will be typeset)"}
${brief.photoId ? `The user asked to feature photo ${brief.photoId}.` : ""}${brief.logoId === "none" ? " The user wants the band name typeset instead of a logo (logoId null)." : brief.logoId ? ` The user asked to use logo ${brief.logoId}.` : ""}

Recipes:
${recipeList}

Allowed fonts (only if overriding a pair): ${FONT_IDS.map((f) => `${f} (${FONTS[f].kind})`).join(", ")}
Treatment modes: original, mono, duotone, tint, threshold.

Return exactly ${count} distinct directions as JSON, each using a different recipe that suits the band and the mood:
{"concepts":[{"recipeId":"...","variant":"... or null","title":"short evocative name","rationale":"2-3 sentences on why this fits and what makes it read as human-made","paletteIndex":0,"palette":null,"fontIndex":0,"fonts":null,"treatment":"mono","mirror":false,"photoId":"... or null","logoId":"... or null","avoids":["which AI tells this direction specifically sidesteps"]}]}
Pick a "variant" where the recipe lists them, choosing the structure that gives this photo and this gig the most presence.
Do not repeat recipes the user has already seen; they are not in the list above.
Only set "palette" (four hex colours) or "fonts" if a custom choice is clearly better than the recipe's options. Respond with JSON only.`;

  try {
    const text = await callClaude(system, [{ type: "text", text: user }], 3000);
    const out = extractJson<{ concepts: ConceptDirection[] }>(text);
    const photoIds = new Set(usablePhotos.map((p) => p.id));
    const logoIds = new Set(usableLogos.map((l) => l.id));
    const concepts = (out.concepts ?? [])
      .filter((c) => RECIPE_MAP[c.recipeId] && !exclude.includes(c.recipeId))
      .filter((c, i, all) => all.findIndex((o) => o.recipeId === c.recipeId) === i)
      .slice(0, count)
      .map<ConceptDirection>((c) => ({
        recipeId: c.recipeId,
        variant: RECIPE_MAP[c.recipeId].variants?.some((v) => v.id === c.variant) ? c.variant : undefined,
        title: String(c.title ?? RECIPE_MAP[c.recipeId].name).slice(0, 80),
        rationale: String(c.rationale ?? "").slice(0, 600),
        paletteIndex: Number.isInteger(c.paletteIndex) ? c.paletteIndex : 0,
        palette:
          c.palette && [c.palette.paper, c.palette.ink, c.palette.accent, c.palette.accent2].every((h) => HEX.test(h ?? ""))
            ? c.palette
            : undefined,
        fontIndex: Number.isInteger(c.fontIndex) ? c.fontIndex : 0,
        fonts: c.fonts && FONT_IDS.includes(c.fonts.display as never) && FONT_IDS.includes(c.fonts.text as never) ? c.fonts : undefined,
        treatment: ["original", "mono", "duotone", "tint", "threshold"].includes(c.treatment ?? "") ? c.treatment : undefined,
        mirror: Boolean(c.mirror),
        photoId: c.photoId && photoIds.has(c.photoId) ? c.photoId : null,
        logoId: c.logoId && logoIds.has(c.logoId) ? c.logoId : null,
        avoids: Array.isArray(c.avoids) ? c.avoids.map(String).slice(0, 5) : [],
      }));
    if (!concepts.length) return jsonError("The model returned no usable concepts", 502);
    return Response.json({ concepts });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "AI request failed", 502);
  }
}
