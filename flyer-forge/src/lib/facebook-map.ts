/** Maps Facebook Page events (Graph API) to calendar gig fields. No imports so it runs under `node --test`. */

export interface FacebookPlace {
  name?: string;
  location?: { street?: string; city?: string; state?: string; zip?: string };
}

export interface FacebookEvent {
  id: string;
  name?: string;
  description?: string;
  start_time?: string;
  end_time?: string;
  is_canceled?: boolean;
  ticket_uri?: string;
  place?: FacebookPlace;
  event_times?: { id?: string; start_time?: string; end_time?: string }[] | { data?: { id?: string; start_time?: string; end_time?: string }[] };
}

export interface FacebookGig {
  uid: string;
  title: string;
  date: string;
  status: "confirmed" | "cancelled";
  venue: string;
  city: string;
  address: string;
  showTime: string;
  tickets: string;
  notes: string;
}

const STREET_START = /^\d+\s+[A-Za-z]/;

function clean(s: string | undefined) {
  return (s ?? "").replace(/\s+/g, " ").trim();
}

/** "Ernie's Tavern Presents The Band" → "Ernie's Tavern"; "Holiday Music at Clifton Oaks" → "Clifton Oaks". */
export function venueFromTitle(title: string) {
  const presents = title.match(/^(.+?)\s+presents\b/i);
  if (presents) return presents[1].trim();
  const t = title.replace(/^Hosting\s+/i, "");
  if (t.includes(" at ")) return t.split(" at ").slice(1).join(" at ").trim();
  return t.split(",")[0].trim();
}

export function placeDetails(title: string, place: FacebookPlace | undefined) {
  let name = clean(place?.name);
  const loc = place?.location ?? {};
  const stateZip = [loc.state, loc.zip].map(clean).filter(Boolean).join(" ");
  let address = [loc.street, loc.city].map(clean).filter(Boolean).concat(stateZip ? [stateZip] : []).join(", ");
  const city = [clean(loc.city), clean(loc.state)].filter(Boolean).join(", ");
  // Ad-hoc places are often just a typed street address with no venue page behind them.
  if (name && !address && STREET_START.test(name)) {
    address = name;
    name = "";
  }
  return { venue: name || venueFromTitle(title), address, city };
}

/** Local calendar date and "7:00 pm" label for a Graph timestamp like 2027-08-21T19:00:00-0400. */
export function localDateTime(value: string | undefined, timeZone: string): { date: string; time: string } | null {
  const v = clean(value);
  if (!v) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return { date: v, time: "" };
  const when = new Date(v.replace(/([+-]\d{2})(\d{2})$/, "$1:$2"));
  if (Number.isNaN(when.getTime())) return null;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "numeric", minute: "2-digit", hourCycle: "h23" })
      .formatToParts(when)
      .map((p) => [p.type, p.value]),
  );
  const hour = Number(parts.hour) % 24;
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${hour % 12 || 12}:${parts.minute} ${hour < 12 ? "am" : "pm"}`,
  };
}

export function mapFacebookEvents(rows: FacebookEvent[], timeZone: string): FacebookGig[] {
  const gigs: FacebookGig[] = [];
  for (const row of rows) {
    const title = clean(row.name);
    if (!title || !row.id) continue;
    const { venue, address, city } = placeDetails(title, row.place);
    const raw = row.event_times;
    const occurrences = (Array.isArray(raw) ? raw : raw?.data) ?? [];
    const times = occurrences.length ? occurrences.map((o) => ({ uid: `facebook:${row.id}:${o.id ?? o.start_time}`, start: o.start_time })) : [{ uid: `facebook:${row.id}`, start: row.start_time }];
    for (const t of times) {
      const when = localDateTime(t.start, timeZone);
      if (!when) continue;
      gigs.push({
        uid: t.uid,
        title: title.toLowerCase() === venue.toLowerCase() ? "" : title,
        date: when.date,
        status: row.is_canceled ? "cancelled" : "confirmed",
        venue,
        city,
        address,
        showTime: when.time,
        tickets: clean(row.ticket_uri),
        notes: (row.description ?? "").trim(),
      });
    }
  }
  return gigs.sort((a, b) => a.date.localeCompare(b.date));
}
