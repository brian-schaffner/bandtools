import { getEvent } from "@/lib/events-repo";
import { ensureDriveTime } from "@/lib/gig-plan";
import { jsonError } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function POST(req: Request, ctx: RouteContext<"/api/events/[id]/drive-time">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const event = await getEvent(id);
  if (!event) return jsonError("Event not found", 404);
  const r = await ensureDriveTime(event, true);
  if (r.error) return jsonError(r.error, 422);
  return Response.json({ event: r.event, estimate: r.estimate });
}
