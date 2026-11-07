import { z } from "zod";
import { aiEnabled, callClaude, extractJson, HARD_RULES, rulebookText } from "@/lib/ai";
import { getBand, jsonError, listAssets, listMembers, listRefs } from "@/lib/repo";
import { RECIPES, RECIPE_MAP } from "@/lib/recipes";
import { parseBill } from "@/lib/bill";
import { sql, toBuffer } from "@/lib/db";
import { sniffRaster } from "@/lib/guard";
import { BriefSchema, FORMATS } from "@/lib/spec";
import { FONT_IDS, FONTS } from "@/lib/fonts";
import type { ConceptDirection } from "@/lib/types";
import { consumeQuota, requireViewer } from "@/lib/guard";

const Body = z.object({
  brief: BriefSchema,
  exclude: z.array(z.string()).default([]),
  count: z.number().int().min(1).max(4).default(3),
  /** A References entry to emulate: every direction becomes a custom bill built on its structure. */
  referenceId: z.string().max(80).nullable().default(null),
});
const TREATMENTS = ["original", "mono", "duotone", "tint", "threshold", "posterize", "halftone"];

const BILL_GUIDE = `Custom bills (recipeId "bill"): instead of a recipe you may set the poster yourself as a stack of lines, the way a show-printer sets wood type. Put it in "bill":
{"paper":"$paper","frame":"none|single|double","texture":"clean|paper|worn|halftone","backdrop":"none|sunburst|burst|rings","backdropColor":"$accent2","margin":0.05,
 "photo":{"at":2,"size":3,"style":"rect|framed|tilted|cutout|cutout-burst|circle","side":"none|left|right","span":3,"treatment":"mono"} or null,
 "lines":[{"role":"presenter|band|tagline|banner|date|weekday|monthday|time|venue|where|price|support|songs|tickets|custom","text":"decorative words, only for custom lines or as the banner/tagline fallback","size":1,"font":"an allowed font","weight":400,"case":"upper|none","color":"$ink|$paper|$accent|$accent2|#hex","align":"center|left|right","effect":"none|outline|inline|shadow|outline-shadow","effectColor":"$accent","arc":0,"backing":"none|band|ribbon","backingColor":"$ink","ornament":"none|stars|rule|rule-above","tracking":0,"width":1}]}
How bills work:
- Lines stack top to bottom and each one fills the measure, so "size" is the line's share of the height: the band 2–3.5, date or venue 1–1.8, details 0.4–0.6. Big jumps in scale between neighbours are what make a bill sing.
- Roles take their words from the brief, so you never type facts; a role with nothing in the brief is skipped. presenter, tagline, banner and songs come from the brief's fields of the same name. "where" is the address or city; weekday/monthday spell the date out ("Saturday" / "November 14").
- "custom" text and the banner/tagline fallbacks are for decorative words only ("Starring", "In person!", "Tonight", "Dance"). Never invent song titles, quotes, acts, prices or dates.
- photo.at is the index of the line the photo sits before (side "none"), or of the first line it sits beside (side "left"/"right", spanning "span" lines). Cut-outs key the backdrop out and only work on photos shot against a plain background; elsewhere they fall back to a rectangle, so prefer "framed" or "rect" for live or bar photos.
- arc (-1..1) bends one title line into an arch; use it on one line at most. backing "band" reverses a line out of a full-width colour bar; "ribbon" sets it on a notched banner.
- Every bill needs date (or weekday + monthday), venue or where, and time lines. Use three to five faces from the allowed fonts.`;
const HEX = /^#[0-9a-fA-F]{6}$/;

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  if (!aiEnabled()) return jsonError("no-key", 503);
  const overQuota = await consumeQuota(viewer, "ai");
  if (overQuota) return overQuota;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid brief");
  const { brief, exclude, count, referenceId } = parsed.data;
  const [band, members, photos, logos, rules, refs] = await Promise.all([
    getBand(),
    listMembers(),
    listAssets("photo"),
    listAssets("logo"),
    rulebookText(),
    referenceId ? listRefs() : Promise.resolve([]),
  ]);
  const reference = referenceId ? refs.find((r) => r.id === referenceId) : undefined;
  if (referenceId && !reference) return jsonError("Reference not found", 404);
  let referenceImage: { media_type: string; data: string } | null = null;
  if (reference?.imageAssetId) {
    const rows = await sql<{ preview: unknown }>("select preview from assets where id = $1", [reference.imageAssetId]);
    const buf = rows[0]?.preview ? toBuffer(rows[0].preview) : null;
    const mime = buf ? sniffRaster(buf) : null;
    if (buf && (mime === "image/jpeg" || mime === "image/png")) referenceImage = { media_type: mime, data: buf.toString("base64") };
  }
  const memberName = (id: string) => members.find((m) => m.id === id)?.name ?? "?";
  const usablePhotos = photos.filter((p) => !p.archived);
  const usableLogos = logos.filter((l) => !l.archived);

  const system = `You are the art director for the band "${band.name || "the band"}"${band.genre ? ` (${band.genre})` : ""}${band.hometown ? ` from ${band.hometown}` : ""}.
You choose design directions for gig flyers that look like they were made by a skilled human designer working in a real print tradition, not by an image generator.

${rules}

${HARD_RULES}

You do not draw anything. You pick a layout recipe (or set a custom bill line by line), palette, font pairing, photo treatment and which of the band's real assets to use. A deterministic layout engine renders it.`;

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

${BILL_GUIDE}

Allowed fonts (for bills, or if overriding a pair): ${FONT_IDS.map((f) => `${f} (${FONTS[f].kind})`).join(", ")}
Treatment modes: ${TREATMENTS.join(", ")} (posterize = three flat inks: dark, accent, light; halftone = newspaper dots).

${
  reference
    ? `The user wants these flyers to look like the reference "${reference.title}"${referenceImage ? " (image attached)" : ""}: ${reference.notes} ${reference.traits.join("; ")}
Make every direction a custom bill (recipeId "bill") that borrows this reference's structure: its line order, scale jumps, kinds of faces, reversed bands, ornaments, photo placement, border and palette. Vary the three so they are clearly different takes. Copy its decorative wording style only; every fact still comes from the brief.`
    : `Return a mix: at most one custom bill, and recipes for the rest, unless the mood clearly calls for a show bill.`
}

Return exactly ${count} distinct directions as JSON:
{"concepts":[{"recipeId":"...","variant":"... or null","title":"short evocative name","rationale":"2-3 sentences on why this fits and what makes it read as human-made","paletteIndex":0,"palette":null,"fontIndex":0,"fonts":null,"treatment":"mono","mirror":false,"photoId":"... or null","logoId":"... or null","avoids":["which AI tells this direction specifically sidesteps"],"bill":null}]}
Pick a "variant" where the recipe lists them, choosing the structure that gives this photo and this gig the most presence.
Do not repeat recipes the user has already seen; they are not in the list above. Custom bills may repeat.
Only set "palette" (four hex colours) or "fonts" if a custom choice is clearly better than the recipe's options; a custom bill should usually set its own palette. Respond with JSON only.`;

  try {
    const content = referenceImage
      ? [{ type: "image" as const, source: { type: "base64" as const, ...referenceImage } }, { type: "text" as const, text: user }]
      : [{ type: "text" as const, text: user }];
    const text = await callClaude(system, content, reference ? 8000 : 5000);
    const out = extractJson<{ concepts: ConceptDirection[] }>(text);
    const photoIds = new Set(usablePhotos.map((p) => p.id));
    const logoIds = new Set(usableLogos.map((l) => l.id));
    const concepts = (out.concepts ?? [])
      .map((c) => {
        if (c.recipeId !== "bill") return { ...c, bill: undefined };
        const bill = parseBill(c.bill);
        // A stack that doesn't parse becomes a built-in show bill rather than being dropped.
        return bill ? { ...c, bill } : { ...c, recipeId: "woodtype", bill: undefined };
      })
      .filter((c) => RECIPE_MAP[c.recipeId] && (c.recipeId === "bill" || !exclude.includes(c.recipeId)))
      .filter((c, i, all) => c.recipeId === "bill" || all.findIndex((o) => o.recipeId === c.recipeId) === i)
      .slice(0, count)
      .map<ConceptDirection>((c) => ({
        recipeId: c.recipeId,
        bill: c.bill,
        seed: Math.floor(Math.random() * 1e9),
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
        treatment: TREATMENTS.includes(c.treatment ?? "") ? c.treatment : undefined,
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
