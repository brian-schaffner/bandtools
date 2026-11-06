import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, mapVersion, VERSION_COLS } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

const Critique = z.object({
  source: z.enum(["checks", "ai"]),
  score: z.number(),
  summary: z.string(),
  issues: z.array(
    z.object({
      severity: z.enum(["pass", "info", "warn", "fail"]),
      area: z.string(),
      note: z.string(),
      fix: z.string().optional(),
    }),
  ),
  createdAt: z.string(),
});

const Patch = z.object({ critique: Critique.nullable().optional(), label: z.string().max(200).optional() });

export async function PATCH(req: Request, ctx: RouteContext<"/api/flyers/[id]/versions/[vid]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id, vid } = await ctx.params;
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid update");
  await sql(
    `update flyer_versions set
       critique = case when $3::boolean then $4::jsonb else critique end,
       label = coalesce($5, label)
     where id = $2 and flyer_id = $1`,
    [id, vid, parsed.data.critique !== undefined, parsed.data.critique ? JSON.stringify(parsed.data.critique) : null, parsed.data.label ?? null],
  );
  const rows = await sql(`select ${VERSION_COLS} from flyer_versions where id = $1`, [vid]);
  return rows[0] ? Response.json(mapVersion(rows[0])) : jsonError("Not found", 404);
}
