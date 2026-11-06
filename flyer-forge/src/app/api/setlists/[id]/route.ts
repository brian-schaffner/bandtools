import { z } from "zod";
import { sql } from "@/lib/db";
import { SetlistItemSchema } from "@/lib/events";
import { mapSetlist, SETLIST_SELECT } from "@/lib/events-repo";
import { jsonError } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request, ctx: RouteContext<"/api/setlists/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const rows = await sql(`${SETLIST_SELECT} where s.id = $1`, [id]);
  if (!rows[0]) return jsonError("Set list not found", 404);
  return Response.json(mapSetlist(rows[0]));
}

const Patch = z.object({
  name: z.string().trim().min(1).max(160).optional(),
  notes: z.string().trim().max(4000).optional(),
  eventId: z.string().nullable().optional(),
  items: z.array(SetlistItemSchema).max(200).optional(),
});

export async function PATCH(req: Request, ctx: RouteContext<"/api/setlists/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(parsed.error.issues[0]?.message ?? "Invalid update");
  const p = parsed.data;
  if (p.eventId) {
    const ev = await sql("select id from events where id = $1", [p.eventId]);
    if (!ev[0]) return jsonError("Event not found", 404);
  }
  const rows = await sql(
    `update setlists set
       name = coalesce($2, name),
       notes = coalesce($3, notes),
       items = coalesce($4::jsonb, items),
       event_id = case when $5 then $6 else event_id end,
       updated_at = now()
     where id = $1 returning id`,
    [id, p.name ?? null, p.notes ?? null, p.items ? JSON.stringify(p.items) : null, p.eventId !== undefined, p.eventId ?? null],
  );
  if (!rows[0]) return jsonError("Set list not found", 404);
  const full = await sql(`${SETLIST_SELECT} where s.id = $1`, [id]);
  return Response.json(mapSetlist(full[0]));
}

export async function DELETE(req: Request, ctx: RouteContext<"/api/setlists/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  await sql("delete from setlists where id = $1", [id]);
  return Response.json({ ok: true });
}
