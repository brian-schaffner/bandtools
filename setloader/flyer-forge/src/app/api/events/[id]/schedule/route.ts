import { z } from "zod";
import { defaultSchedule, ScheduleItemSchema } from "@/lib/events";
import { getEvent, replaceSchedule } from "@/lib/events-repo";
import { jsonError } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

const Body = z.object({ items: z.array(ScheduleItemSchema).max(60).optional(), template: z.literal("default").optional() });

export async function PUT(req: Request, ctx: RouteContext<"/api/events/[id]/schedule">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(parsed.error.issues[0]?.message ?? "Invalid schedule");
  const event = await getEvent(id);
  if (!event) return jsonError("Event not found", 404);
  const items = parsed.data.template ? defaultSchedule(event) : (parsed.data.items ?? []);
  return Response.json(await replaceSchedule(id, items));
}
