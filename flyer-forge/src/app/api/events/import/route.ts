import { z } from "zod";
import { sql } from "@/lib/db";
import { EventFieldsSchema, parseIcs } from "@/lib/events";
import { insertEvent, mapEvent, replaceSchedule } from "@/lib/events-repo";
import { jsonError } from "@/lib/repo";
import { consumeQuota, countRows, requireViewer, STORAGE, tooMany } from "@/lib/guard";

const MAX_IMPORT = 300;
const Body = z.object({ ics: z.string().max(500_000), onlyMatching: z.string().trim().max(80).default("") });

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Upload an .ics calendar file (under 500 KB)");
  const overQuota = await consumeQuota(viewer, "import");
  if (overQuota) return overQuota;
  const filter = parsed.data.onlyMatching.toLowerCase();
  const all = parseIcs(parsed.data.ics);
  if (!all.length) return jsonError("No events found in that file");
  const items = filter ? all.filter((e) => `${e.summary} ${e.location} ${e.description}`.toLowerCase().includes(filter)) : all;

  // A filter word used as a title prefix ("Gig - Strange Matter") is dropped from the title.
  const prefix = filter ? new RegExp(`^\\s*${filter.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[-:–—|]\\s*`, "i") : null;
  let created = 0;
  let updated = 0;
  let unchanged = 0;
  if (items.length > MAX_IMPORT) return jsonError(`That file has ${items.length} matching events; import at most ${MAX_IMPORT} at a time (use the filter to narrow it).`);
  if ((await countRows("events")) + items.length > STORAGE.eventsTotal) return tooMany("gigs");
  for (const it of items) {
    const own = it.uid.match(/^(event_[a-z0-9]+)@gig-flyer-studio$/);
    if (own && (await sql("select 1 from events where id = $1", [own[1]]))[0]) {
      unchanged++;
      continue;
    }
    const [venue, ...rest] = it.location.split(",").map((s) => s.trim());
    const fields = EventFieldsSchema.parse({
      title: (prefix ? it.summary.replace(prefix, "") : it.summary).slice(0, 160),
      date: it.date,
      status: it.status,
      venue: (venue || "").slice(0, 160),
      address: it.location.slice(0, 300),
      city: rest.slice(-2).join(", ").slice(0, 160),
      notes: it.description.slice(0, 4000),
    });
    if (fields.title.toLowerCase() === fields.venue.toLowerCase()) fields.title = "";
    const existing = await sql("select * from events where external_uid = $1", [it.uid]);
    if (existing[0]) {
      await sql(
        "update events set title = $2, date = $3, status = $4, venue = $5, address = $6, notes = $7, updated_at = now() where id = $1",
        [existing[0].id, fields.title, fields.date, fields.status, fields.venue, fields.address, fields.notes],
      );
      updated++;
    } else {
      const ev = await insertEvent(fields, it.uid);
      if (it.time) await replaceSchedule(ev.id, [{ time: it.time, label: "Calendar start", kind: "other", notes: "" }]);
      created++;
    }
  }
  const sample = await sql("select * from events order by updated_at desc limit 1");
  return Response.json({ found: all.length, matched: items.length, created, updated, unchanged, latest: sample[0] ? mapEvent(sample[0]) : null });
}
