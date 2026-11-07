import { sql } from "@/lib/db";
import { EventFieldsSchema } from "@/lib/events";
import { insertEvent, replaceSchedule } from "@/lib/events-repo";
import { fetchWebsiteListings } from "@/lib/band-website";
import { bandTimeZone, facebookConfig, fetchFacebookEvents } from "@/lib/facebook";
import { mapFacebookEvents } from "@/lib/facebook-map";
import { consumeQuota, countRows, requireViewer, STORAGE, tooMany } from "@/lib/guard";
import { jsonError } from "@/lib/repo";
import { matchListing } from "@/lib/website-listings";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  return Response.json({ configured: facebookConfig() !== null }, { headers: { "cache-control": "private, no-store" } });
}

/**
 * Pulls upcoming gigs from the band's Facebook Page. Re-syncing updates gigs it created before; notes typed here are kept.
 * City, address and end time come from Facebook when it has them, else the band website's listing, and are never blanked.
 */
export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const cfg = facebookConfig();
  if (!cfg) return jsonError("Facebook isn't connected on this server", 503);
  const overQuota = await consumeQuota(viewer, "import");
  if (overQuota) return overQuota;

  let gigs;
  try {
    gigs = mapFacebookEvents(await fetchFacebookEvents(cfg), bandTimeZone());
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Facebook sync failed", 502);
  }

  const listings = await fetchWebsiteListings();
  let created = 0;
  let updated = 0;
  let unchanged = 0;
  for (const g of gigs) {
    const existing = (await sql<Record<string, unknown>>("select * from events where external_uid = $1", [g.uid]))[0];
    const site = matchListing(g, listings);
    const keep = (fb: string, col: string, web: string | undefined) => fb || String(existing?.[col] ?? "") || web || "";
    const fields = EventFieldsSchema.parse({
      title: g.title,
      date: g.date,
      status: g.status,
      venue: g.venue,
      city: keep(g.city, "city", site?.city),
      address: keep(g.address, "address", site?.address),
      showTime: g.showTime,
      endTime: keep(g.endTime, "end_time", site?.end),
      tickets: g.tickets,
      notes: g.notes,
    });
    if (existing) {
      const same =
        existing.title === fields.title && existing.date === fields.date && existing.status === fields.status && existing.venue === fields.venue &&
        existing.city === fields.city && existing.address === fields.address && existing.show_time === fields.showTime &&
        existing.end_time === fields.endTime && existing.tickets === fields.tickets;
      if (same) {
        unchanged++;
        continue;
      }
      await sql(
        "update events set title = $2, date = $3, status = $4, venue = $5, city = $6, address = $7, show_time = $8, end_time = $9, tickets = $10, updated_at = now() where id = $1",
        [existing.id, fields.title, fields.date, fields.status, fields.venue, fields.city, fields.address, fields.showTime, fields.endTime, fields.tickets],
      );
      updated++;
    } else {
      if ((await countRows("events")) >= STORAGE.eventsTotal) return tooMany("gigs");
      const ev = await insertEvent(fields, g.uid);
      if (fields.showTime) await replaceSchedule(ev.id, [{ time: fields.showTime, label: "Show (from Facebook)", kind: "set", notes: "" }]);
      created++;
    }
  }
  return Response.json({ found: gigs.length, created, updated, unchanged });
}
