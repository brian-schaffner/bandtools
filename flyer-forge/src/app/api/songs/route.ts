import { connection } from "next/server";
import { sql } from "@/lib/db";
import { songKey, todayIso, type SetlistItem, type SongStat } from "@/lib/events";
import { requireViewer } from "@/lib/guard";

/** Song history across set lists filed under gigs that have already happened; `exclude` leaves out one set list. */
export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  const exclude = new URL(req.url).searchParams.get("exclude") ?? "";
  const rows = await sql<{ items: unknown; date: string }>(
    `select s.items, e.date from setlists s join events e on e.id = s.event_id
     where e.status <> 'cancelled' and e.date <= $1 and s.id <> $2`,
    [todayIso(), exclude],
  );
  const stats = new Map<string, SongStat>();
  for (const r of rows) {
    const items = (typeof r.items === "string" ? JSON.parse(r.items) : r.items) as SetlistItem[];
    const seen = new Set<string>();
    for (const it of items) {
      if (it.type !== "song") continue;
      const k = songKey(it.title);
      if (!k || seen.has(k)) continue;
      seen.add(k);
      const s = stats.get(k) ?? { title: it.title, count: 0, lastDate: null };
      s.count += 1;
      if (!s.lastDate || r.date > s.lastDate) s.lastDate = r.date;
      stats.set(k, s);
    }
  }
  return Response.json(Object.fromEntries(stats));
}
