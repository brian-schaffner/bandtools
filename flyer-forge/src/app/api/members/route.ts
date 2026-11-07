import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, listMembers, newId } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

const Body = z.object({ name: z.string().trim().min(1).max(80), role: z.string().max(80).default("") });

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Member name is required");
  const [{ n }] = await sql<{ n: number }>("select coalesce(max(sort), 0) + 1 as n from members");
  const id = newId("mem");
  await sql("insert into members (id, name, role, sort) values ($1, $2, $3, $4)", [id, parsed.data.name, parsed.data.role.trim(), Number(n)]);
  return Response.json(await listMembers());
}
