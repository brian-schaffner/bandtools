import { z } from "zod";
import { EventFieldsSchema } from "@/lib/events";
import { insertEvent, mapEvent, replaceSchedule } from "@/lib/events-repo";
import { sql } from "@/lib/db";
import { consumeQuota, countRows, requireViewer, STORAGE, tooMany } from "@/lib/guard";

/** Payload from gig-flyers `GigEvent.to_dict()` via Setloader `/band-calendar`. */
const BandGigSchema = z.object({
  gig_id: z.string(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  title: z.string(),
  venue: z.string(),
  time: z.string().optional().default(""),
  address: z.string().optional().default(""),
  suggested_name: z.string().optional().default(""),
  band: z.string().optional().default(""),
});

/**
 * One-way sync: pull upcoming gigs from the Band Tools shared calendar (lindseylane.com scrape + cache)
 * into Flyer Forge events. Re-running updates rows with the same external_uid.
 */
export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;

  const overQuota = await consumeQuota(viewer, "import");
  if (overQuota) return overQuota;

  const baseUrl = (process.env.SETLOADER_INTERNAL_URL ?? "http://127.0.0.1:8002").replace(/\/$/, "");
  const secret = process.env.SECRET?.trim() ?? "";
  if (!secret) return Response.json({ error: "SECRET is not configured" }, { status: 503 });

  const res = await fetch(`${baseUrl}/band-calendar`, { headers: { "X-Secret": secret } });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    return Response.json({ error: `Band calendar unavailable (${res.status})`, detail: text.slice(0, 200) }, { status: 502 });
  }
  const raw = await res.json();
  const parsed = z.array(BandGigSchema).safeParse(raw);
  if (!parsed.success) {
    return Response.json({ error: "Unexpected calendar JSON" }, { status: 502 });
  }

  const gigs = parsed.data;
  if ((await countRows("events")) + gigs.length > STORAGE.eventsTotal) {
    return tooMany("gigs");
  }

  let created = 0;
  let updated = 0;

  for (const g of gigs) {
    const externalUid = `bandtools:${g.gig_id}`;
    const title = (g.title || g.suggested_name || `${g.band || "Show"} at ${g.venue}`).slice(0, 160);
    const fields = EventFieldsSchema.parse({
      title,
      date: g.date,
      status: "confirmed",
      venue: g.venue.slice(0, 160),
      city: "",
      address: g.address.slice(0, 300),
      showTime: g.time.slice(0, 40),
      notes: `Synced from Band Tools calendar (${g.gig_id}).`,
    });

    const existing = await sql("select id from events where external_uid = $1", [externalUid]);
    const rowId = existing[0]?.id as string | undefined;

    if (rowId) {
      await sql(
        `update events set title = $2, date = $3, venue = $4, address = $5, show_time = $6, notes = $7, updated_at = now() where id = $1`,
        [rowId, fields.title, fields.date, fields.venue, fields.address, fields.showTime, fields.notes],
      );
      if (g.time) {
        await replaceSchedule(rowId, [{ time: g.time, label: "Show", kind: "set", notes: "" }]);
      }
      updated++;
    } else {
      const ev = await insertEvent(fields, externalUid);
      if (g.time) {
        await replaceSchedule(ev.id, [{ time: g.time, label: "Show", kind: "set", notes: "" }]);
      }
      created++;
    }
  }

  const sample = await sql("select * from events order by updated_at desc limit 1");
  return Response.json({
    pulled: gigs.length,
    created,
    updated,
    latest: sample[0] ? mapEvent(sample[0]) : null,
  });
}
