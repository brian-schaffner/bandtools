import { z } from "zod";
import { sql } from "@/lib/db";
import { getAsset, jsonError } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request, ctx: RouteContext<"/api/assets/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const asset = await getAsset(id);
  return asset ? Response.json(asset) : jsonError("Not found", 404);
}

const Patch = z.object({
  name: z.string().max(160).optional(),
  photoKind: z.enum(["group", "individual", "live", "other"]).optional(),
  memberIds: z.array(z.string()).optional(),
  credit: z.string().max(160).optional(),
  notes: z.string().max(2000).optional(),
  focalX: z.number().min(0).max(1).optional(),
  focalY: z.number().min(0).max(1).optional(),
  isPrimary: z.boolean().optional(),
  archived: z.boolean().optional(),
});

/** Only metadata is editable. The stored bytes of an original never change after upload. */
export async function PATCH(req: Request, ctx: RouteContext<"/api/assets/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid update");
  const p = parsed.data;
  const asset = await getAsset(id);
  if (!asset) return jsonError("Not found", 404);
  if (p.isPrimary) await sql("update assets set is_primary = false where kind = $1", [asset.kind]);
  await sql(
    `update assets set
       name = coalesce($2, name),
       photo_kind = coalesce($3, photo_kind),
       member_ids = coalesce($4::jsonb, member_ids),
       credit = coalesce($5, credit),
       notes = coalesce($6, notes),
       focal_x = coalesce($7, focal_x),
       focal_y = coalesce($8, focal_y),
       is_primary = coalesce($9, is_primary),
       archived = coalesce($10, archived)
     where id = $1`,
    [
      id,
      p.name?.trim() ?? null,
      p.photoKind ?? null,
      p.memberIds ? JSON.stringify(p.memberIds) : null,
      p.credit?.trim() ?? null,
      p.notes ?? null,
      p.focalX ?? null,
      p.focalY ?? null,
      p.isPrimary ?? null,
      p.archived ?? null,
    ],
  );
  return Response.json(await getAsset(id));
}

export async function DELETE(req: Request, ctx: RouteContext<"/api/assets/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  await sql("delete from assets where id = $1", [id]);
  await sql("update style_refs set image_asset_id = null where image_asset_id = $1", [id]);
  return Response.json({ ok: true });
}
