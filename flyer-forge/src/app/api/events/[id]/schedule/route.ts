import { z } from "zod";
import { ScheduleItemSchema } from "@/lib/events";
import { getEvent, listSchedule, replaceSchedule } from "@/lib/events-repo";
import { buildScheduleFromRules } from "@/lib/gig-plan";
import { jsonError } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

const Body = z.object({ items: z.array(ScheduleItemSchema).max(60).optional(), template: z.literal("rules").optional() });

export async function PUT(req: Request, ctx: RouteContext<"/api/events/[id]/schedule">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(parsed.error.issues[0]?.message ?? "Invalid schedule");
  if (parsed.data.template) {
    const built = await buildScheduleFromRules(id);
    if (!built) return jsonError("Event not found", 404);
    return Response.json({
      event: built.event,
      items: built.items ?? (await listSchedule(id)),
      estimate: built.estimate,
      steps: built.plan.steps,
      problems: built.problems,
    });
  }
  if (!(await getEvent(id))) return jsonError("Event not found", 404);
  return Response.json(await replaceSchedule(id, parsed.data.items ?? []));
}
