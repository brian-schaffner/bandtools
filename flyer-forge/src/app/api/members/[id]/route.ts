import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, listMembers } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

const Body = z.object({ name: z.string().trim().min(1).max(80), role: z.string().max(80).default("") });

export async function PATCH(req: Request, ctx: RouteContext<"/api/members/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Member name is required");
  await sql("update members set name = $2, role = $3 where id = $1", [id, parsed.data.name, parsed.data.role.trim()]);
  return Response.json(await listMembers());
}

export async function DELETE(req: Request, ctx: RouteContext<"/api/members/[id]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  await sql("delete from members where id = $1", [id]);
  await sql("update assets set member_ids = member_ids - $1::text where member_ids ? $1", [id]);
  return Response.json(await listMembers());
}
