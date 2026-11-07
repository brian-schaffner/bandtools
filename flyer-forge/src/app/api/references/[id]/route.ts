import { z } from "zod";
import { deleteAssets } from "@/lib/chunk-store";
import { sql } from "@/lib/db";
import { jsonError, mapRef } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

const Patch = z.object({
  kind: z.enum(["avoid", "inspire"]).optional(),
  title: z.string().trim().min(1).max(160).optional(),
  notes: z.string().max(4000).optional(),
  traits: z.array(z.string().trim().min(1).max(240)).max(30).optional(),
  recipeId: z.string().nullable().optional(),
  imageAssetId: z.string().nullable().optional(),
  archived: z.boolean().optional(),
});

export async function PATCH(req: Request, ctx: RouteContext<"/api/references/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid update");
  const p = parsed.data;
  const rows = await sql(
    `update style_refs set
       kind = coalesce($2, kind),
       title = coalesce($3, title),
       notes = coalesce($4, notes),
       traits = coalesce($5::jsonb, traits),
       recipe_id = case when $6::boolean then $7 else recipe_id end,
       image_asset_id = case when $8::boolean then $9 else image_asset_id end,
       archived = coalesce($10, archived),
       updated_at = now()
     where id = $1 returning *`,
    [
      id,
      p.kind ?? null,
      p.title ?? null,
      p.notes ?? null,
      p.traits ? JSON.stringify(p.traits) : null,
      p.recipeId !== undefined,
      p.recipeId ?? null,
      p.imageAssetId !== undefined,
      p.imageAssetId ?? null,
      p.archived ?? null,
    ],
  );
  if (!rows[0]) return jsonError("Not found", 404);
  return Response.json(mapRef(rows[0]));
}

export async function DELETE(req: Request, ctx: RouteContext<"/api/references/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const rows = await sql<{ image_asset_id: string | null }>("delete from style_refs where id = $1 returning image_asset_id", [id]);
  if (rows[0]?.image_asset_id) await deleteAssets("id = $1 and kind = 'reference'", [rows[0].image_asset_id]);
  return Response.json({ ok: true });
}
