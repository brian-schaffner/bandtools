import { connection } from "next/server";
import { z } from "zod";
import { sql } from "@/lib/db";
import { parseSetlistText, SetlistItemSchema } from "@/lib/events";
import { mapSetlist, SETLIST_SELECT } from "@/lib/events-repo";
import { jsonError, newId } from "@/lib/repo";
import { countRows, requireViewer, STORAGE, tooMany } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  const event = new URL(req.url).searchParams.get("event");
  const rows = event
    ? await sql(`${SETLIST_SELECT} where s.event_id = $1 order by s.created_at`, [event])
    : await sql(`${SETLIST_SELECT} order by coalesce(e.date, to_char(s.created_at, 'YYYY-MM-DD')) desc, s.created_at desc`);
  return Response.json(rows.map(mapSetlist));
}

const Body = z.object({
  name: z.string().trim().min(1).max(160),
  eventId: z.string().nullable().default(null),
  notes: z.string().trim().max(4000).default(""),
  items: z.array(SetlistItemSchema).max(200).optional(),
  text: z.string().max(100_000).optional(),
  source: z.enum(["manual", "paste", "file", "copy"]).default("manual"),
});

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(parsed.error.issues[0]?.message ?? "Invalid set list");
  if ((await countRows("setlists")) >= STORAGE.setlistsTotal) return tooMany("set lists");
  const b = parsed.data;
  const items = b.items ?? (b.text ? parseSetlistText(b.text) : []);
  if (b.text && !items.length) return jsonError("Couldn't find any songs in that text");
  if (b.eventId) {
    const ev = await sql("select id from events where id = $1", [b.eventId]);
    if (!ev[0]) return jsonError("Event not found", 404);
  }
  const id = newId("setlist");
  await sql("insert into setlists (id, event_id, name, notes, items, source) values ($1, $2, $3, $4, $5::jsonb, $6)", [
    id,
    b.eventId,
    b.name,
    b.notes,
    JSON.stringify(items.slice(0, 200)),
    b.source,
  ]);
  const rows = await sql(`${SETLIST_SELECT} where s.id = $1`, [id]);
  return Response.json(mapSetlist(rows[0]));
}
