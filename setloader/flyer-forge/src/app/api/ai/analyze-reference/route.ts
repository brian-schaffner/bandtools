import { z } from "zod";
import { aiEnabled, callClaude, extractJson } from "@/lib/ai";
import { jsonError } from "@/lib/repo";
import { RECIPES } from "@/lib/recipes";
import { consumeQuota, requireViewer } from "@/lib/guard";

const Body = z.object({ image: z.string().max(3_000_000), kind: z.enum(["avoid", "inspire"]) });

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  if (!aiEnabled()) return jsonError("no-key", 503);
  const overQuota = await consumeQuota(viewer, "ai");
  if (overQuota) return overQuota;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid request");
  const { image, kind } = parsed.data;
  const m = /^data:(image\/(?:jpeg|png));base64,(.+)$/.exec(image);
  if (!m) return jsonError("Expected a JPEG or PNG data URL");

  const ask =
    kind === "avoid"
      ? `This is an AI-generated gig flyer. List the specific visual tells that make it read as AI-made, phrased as rules to avoid (e.g. "No glossy rim lighting on every surface").`
      : `This is a traditionally designed gig flyer or poster. Identify the print tradition and list the concrete, reusable design moves (grid, type, palette, photo treatment, texture, composition), phrased as rules to follow.`;

  try {
    const text = await callClaude(
      "You are a design historian and gig-poster designer. Be specific and concrete; avoid vague adjectives.",
      [
        { type: "image", source: { type: "base64", media_type: m[1], data: m[2] } },
        {
          type: "text",
          text: `${ask}
Known recipes: ${RECIPES.map((r) => `${r.id} (${r.name})`).join(", ")}.
Return JSON only: {"title":"short name","notes":"2-3 sentences","traits":["4-8 rules"],"recipeId":"closest recipe id or null"}`,
        },
      ],
      1500,
    );
    const out = extractJson<{ title: string; notes: string; traits: string[]; recipeId: string | null }>(text);
    return Response.json({
      title: String(out.title ?? "").slice(0, 160),
      notes: String(out.notes ?? "").slice(0, 2000),
      traits: (out.traits ?? []).map((t) => String(t).slice(0, 240)).slice(0, 12),
      recipeId: RECIPES.some((r) => r.id === out.recipeId) ? out.recipeId : null,
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "AI request failed", 502);
  }
}
