import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, mapFlyer, mapVersion, VERSION_COLS } from "@/lib/repo";
import { BriefSchema } from "@/lib/spec";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request, ctx: RouteContext<"/api/flyers/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const rows = await sql("select * from flyers where id = $1", [id]);
  if (!rows[0]) return jsonError("Flyer not found", 404);
  const versions = await sql(`select ${VERSION_COLS} from flyer_versions where flyer_id = $1 order by created_at`, [id]);
  return Response.json({ flyer: mapFlyer(rows[0]), versions: versions.map(mapVersion) });
}

const Patch = z.object({
  title: z.string().trim().min(1).max(160).optional(),
  brief: BriefSchema.optional(),
  currentVersionId: z.string().optional(),
  archived: z.boolean().optional(),
  eventId: z.string().nullable().optional(),
});

export async function PATCH(req: Request, ctx: RouteContext<"/api/flyers/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid update");
  const p = parsed.data;
  const rows = await sql(
    `update flyers set
       title = coalesce($2, title),
       brief = coalesce($3::jsonb, brief),
       current_version_id = coalesce($4, current_version_id),
       archived = coalesce($5, archived),
       event_id = case when $6 then $7 else event_id end,
       updated_at = now()
     where id = $1 returning *`,
    [id, p.title ?? null, p.brief ? JSON.stringify(p.brief) : null, p.currentVersionId ?? null, p.archived ?? null, p.eventId !== undefined, p.eventId ?? null],
  );
  if (!rows[0]) return jsonError("Flyer not found", 404);
  return Response.json(mapFlyer(rows[0]));
}

export async function DELETE(req: Request, ctx: RouteContext<"/api/flyers/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  await sql("delete from flyers where id = $1", [id]);
  return Response.json({ ok: true });
}
