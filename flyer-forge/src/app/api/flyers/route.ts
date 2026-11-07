import { connection } from "next/server";
import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, mapFlyer, newId } from "@/lib/repo";
import { BriefSchema } from "@/lib/spec";
import { briefToEventFields } from "@/lib/events";
import { findOrCreateEvent, getEvent } from "@/lib/events-repo";
import { countRows, requireViewer, STORAGE, tooMany } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  const rows = await sql(
    `select f.*, v.spec->>'format' as format from flyers f
     left join flyer_versions v on v.id = f.current_version_id
     where not f.archived order by f.updated_at desc`,
  );
  return Response.json(rows.map((r) => ({ ...mapFlyer(r), format: r.format ?? null })));
}

const Body = z.object({ title: z.string().trim().min(1).max(160), brief: BriefSchema, eventId: z.string().nullable().optional() });

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("A title and gig details are required");
  if ((await countRows("flyers")) >= STORAGE.flyersTotal) return tooMany("flyers");
  const { brief, title } = parsed.data;
  let eventId = parsed.data.eventId ?? null;
  if (eventId && !(await getEvent(eventId))) return jsonError("Event not found", 404);
  if (!eventId && /^\d{4}-\d{2}-\d{2}$/.test(brief.date)) eventId = (await findOrCreateEvent(briefToEventFields(brief))).id;
  const id = newId("flyer");
  const rows = await sql("insert into flyers (id, title, brief, event_id) values ($1, $2, $3::jsonb, $4) returning *", [
    id,
    title,
    JSON.stringify(brief),
    eventId,
  ]);
  return Response.json(mapFlyer(rows[0]));
}
