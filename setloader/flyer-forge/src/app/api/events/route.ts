import { connection } from "next/server";
import { z } from "zod";
import { EventFieldsSchema, defaultSchedule } from "@/lib/events";
import { insertEvent, listEvents, replaceSchedule } from "@/lib/events-repo";
import { jsonError } from "@/lib/repo";
import { countRows, requireViewer, STORAGE, tooMany } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  return Response.json(await listEvents());
}

const Body = EventFieldsSchema.extend({ withSchedule: z.boolean().default(false) });

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(parsed.error.issues[0]?.message ?? "A date is required");
  if ((await countRows("events")) >= STORAGE.eventsTotal) return tooMany("gigs");
  const { withSchedule, ...fields } = parsed.data;
  const event = await insertEvent(fields);
  if (withSchedule) await replaceSchedule(event.id, defaultSchedule(fields));
  return Response.json(event);
}
