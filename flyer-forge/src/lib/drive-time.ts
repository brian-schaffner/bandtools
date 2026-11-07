import "server-only";

const UA = "BandTools-FlyerForge/1.0 (gig scheduling)";

type Point = { lat: number; lon: number; label: string };

const geoCache = new Map<string, Point | null>();
let lastGeocode = 0;

/** OpenStreetMap Nominatim allows one request a second. */
async function geocode(q: string): Promise<Point | null> {
  const key = q.trim().toLowerCase();
  if (!key) return null;
  if (geoCache.has(key)) return geoCache.get(key)!;
  const wait = lastGeocode + 1100 - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastGeocode = Date.now();
  const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(q)}`;
  const res = await fetch(url, { headers: { "user-agent": UA, "accept-language": "en" }, signal: AbortSignal.timeout(10_000), cache: "no-store" });
  if (!res.ok) throw new Error(`Address lookup failed (${res.status})`);
  const hits = (await res.json()) as { lat: string; lon: string; display_name: string }[];
  const p = hits[0] ? { lat: Number(hits[0].lat), lon: Number(hits[0].lon), label: hits[0].display_name } : null;
  geoCache.set(key, p);
  return p;
}

export interface DriveEstimate {
  minutes: number;
  miles: number;
  /** What the venue lookup actually matched, so a wrong guess is visible. */
  to: string;
  /** True when only the city could be found, not the venue itself. */
  approximate: boolean;
}

export async function estimateDrive(home: string, venue: { venue: string; address: string; city: string }): Promise<DriveEstimate> {
  const from = await geocode(home);
  if (!from) throw new Error(`Couldn't find the band's home address "${home}" on the map`);
  const tries: [string, boolean][] = [
    [venue.address, false],
    [[venue.venue, venue.city].filter(Boolean).join(", "), false],
    [venue.city, true],
  ];
  let to: Point | null = null;
  let approximate = false;
  for (const [q, approx] of tries) {
    if (!q.trim()) continue;
    to = await geocode(q);
    if (to) {
      approximate = approx;
      break;
    }
  }
  if (!to) throw new Error("Couldn't find the venue on the map; add its street address");
  const url = `https://router.project-osrm.org/route/v1/driving/${from.lon},${from.lat};${to.lon},${to.lat}?overview=false`;
  const res = await fetch(url, { headers: { "user-agent": UA }, signal: AbortSignal.timeout(15_000), cache: "no-store" });
  if (!res.ok) throw new Error(`Route lookup failed (${res.status})`);
  const data = (await res.json()) as { code: string; routes?: { duration: number; distance: number }[] };
  const route = data.routes?.[0];
  if (data.code !== "Ok" || !route) throw new Error("No driving route found");
  return { minutes: Math.ceil(route.duration / 60), miles: Math.round((route.distance / 1609.344) * 10) / 10, to: to.label, approximate };
}
