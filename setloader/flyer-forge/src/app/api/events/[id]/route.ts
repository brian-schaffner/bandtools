import { EventFieldsSchema } from "@/lib/events";
import { getEvent, listSchedule, mapSetlist, SETLIST_SELECT, updateEvent } from "@/lib/events-repo";
import { sql } from "@/lib/db";
import { jsonError, mapFlyer } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request, ctx: RouteContext<"/api/events/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const event = await getEvent(id);
  if (!event) return jsonError("Event not found", 404);
  const [schedule, flyers, setlists] = await Promise.all([
    listSchedule(id),
    sql(
      `select f.*, v.spec->>'format' as format from flyers f
       left join flyer_versions v on v.id = f.current_version_id
       where f.event_id = $1 and not f.archived order by f.created_at`,
      [id],
    ),
    sql(`${SETLIST_SELECT} where s.event_id = $1 order by s.created_at`, [id]),
  ]);
  return Response.json({
    event,
    schedule,
    flyers: flyers.map((r) => ({ ...mapFlyer(r), format: r.format ?? null })),
    setlists: setlists.map(mapSetlist),
  });
}

export async function PATCH(req: Request, ctx: RouteContext<"/api/events/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = EventFieldsSchema.partial().safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(parsed.error.issues[0]?.message ?? "Invalid update");
  const event = await updateEvent(id, parsed.data);
  if (!event) return jsonError("Event not found", 404);
  return Response.json(event);
}

export async function DELETE(req: Request, ctx: RouteContext<"/api/events/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  await sql("delete from events where id = $1", [id]);
  return Response.json({ ok: true });
}
