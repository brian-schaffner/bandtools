import { z } from "zod";
import { aiEnabled, callClaude, extractJson, HARD_RULES, rulebookText } from "@/lib/ai";
import { jsonError, listAssets } from "@/lib/repo";
import { FONT_IDS } from "@/lib/fonts";
import { SpecSchema } from "@/lib/spec";
import { consumeQuota, requireViewer } from "@/lib/guard";

const Body = z.object({ spec: SpecSchema, instruction: z.string().trim().min(1).max(1000) });

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  if (!aiEnabled()) return jsonError("no-key", 503);
  const overQuota = await consumeQuota(viewer, "ai");
  if (overQuota) return overQuota;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid edit request");
  const { spec, instruction } = parsed.data;
  const [photos, logos, rules] = await Promise.all([listAssets("photo"), listAssets("logo"), rulebookText()]);

  const system = `You edit gig-flyer layout specs. The spec is JSON rendered by a deterministic engine.
Coordinates x, y, w, h are fractions of the canvas (x/w of width, y/h of height). Text "size" is a fraction of canvas width; "fill": true scales text to fill its box width. Colours are hex or palette tokens $paper, $ink, $accent, $accent2.
Photo layers crop with fit/zoom/focusX/focusY and colour-map with "treatment" (modes original, mono, duotone, tint, threshold). Logos may be recoloured ("recolor" hex/token, "recolorMode" tone|solid) or left null for original colours.

${HARD_RULES}

${rules}

Make the smallest change that fully satisfies the request. Keep layer ids stable. Only use fonts from: ${FONT_IDS.join(", ")}.
Only use asset ids from the lists provided.`;

  const user = `Current spec:
${JSON.stringify(spec)}

Photos: ${photos.filter((p) => !p.archived).map((p) => `${p.id} "${p.name}" ${p.photoKind} ${(p.width / p.height).toFixed(2)}:1`).join("; ") || "none"}
Logos: ${logos.filter((l) => !l.archived).map((l) => `${l.id} "${l.name}" ${(l.width / l.height).toFixed(2)}:1`).join("; ") || "none"}

Request: ${instruction}

Respond with JSON only: {"note":"one sentence describing what you changed","spec":{...full updated spec...}}`;

  try {
    const text = await callClaude(system, [{ type: "text", text: user }], 8000);
    const out = extractJson<{ note?: string; spec: unknown }>(text);
    const next = SpecSchema.safeParse(out.spec);
    if (!next.success) return jsonError("The model's edit did not pass validation; nothing was changed", 502);
    const ids = new Set([...photos, ...logos].map((a) => a.id));
    for (const l of next.data.layers) {
      if ((l.type === "photo" || l.type === "logo") && l.assetId && !ids.has(l.assetId)) {
        return jsonError("The model referenced an asset that does not exist; nothing was changed", 502);
      }
    }
    return Response.json({ note: String(out.note ?? instruction).slice(0, 300), spec: next.data });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "AI request failed", 502);
  }
}
