import { connection } from "next/server";
import { buildIcs } from "@/lib/events";
import { listEvents, listSchedule } from "@/lib/events-repo";
import { getBand } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  const [events, band] = await Promise.all([listEvents(), getBand()]);
  const withSchedule = await Promise.all(events.map(async (e) => ({ ...e, schedule: await listSchedule(e.id) })));
  const slug = (band.name || "band").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return new Response(buildIcs(withSchedule, band.name), {
    headers: {
      "content-type": "text/calendar; charset=utf-8",
      "content-disposition": `attachment; filename="${slug || "band"}-gigs.ics"`,
    },
  });
}
