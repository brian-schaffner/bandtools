import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, mapVersion, newId, VERSION_COLS } from "@/lib/repo";
import { SpecSchema } from "@/lib/spec";
import { requireViewer, sniffRaster, STORAGE, tooMany } from "@/lib/guard";

const Meta = z.object({
  parentId: z.string().nullable().default(null),
  label: z.string().max(200).default(""),
  source: z.enum(["concept", "edit", "evolve", "manual", "ai-edit"]),
  spec: SpecSchema,
  makeCurrent: z.boolean().default(true),
});

/** Multipart: `meta` JSON plus an optional `thumb` image. */
export async function POST(req: Request, ctx: RouteContext<"/api/flyers/[id]/versions">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const form = await req.formData().catch(() => null);
  if (!form) return jsonError("Expected multipart body");
  let raw: unknown = null;
  try {
    raw = JSON.parse(String(form.get("meta") ?? "null"));
  } catch {
    return jsonError("Invalid version payload");
  }
  const parsed = Meta.safeParse(raw);
  if (!parsed.success) return jsonError("The design spec failed validation");
  const exists = await sql("select 1 from flyers where id = $1", [id]);
  if (!exists[0]) return jsonError("Flyer not found", 404);
  const thumb = form.get("thumb");
  const thumbBuf = thumb instanceof Blob ? Buffer.from(await thumb.arrayBuffer()) : null;
  if (thumbBuf && thumbBuf.byteLength > 1024 * 1024) return jsonError("Thumbnail too large");
  if (thumbBuf && !sniffRaster(thumbBuf)) return jsonError("Thumbnail must be a JPEG, PNG or WebP image");
  const count = await sql<{ n: string }>("select count(*) as n from flyer_versions where flyer_id = $1", [id]);
  if (Number(count[0]?.n ?? 0) >= STORAGE.versionsPerFlyer) return tooMany("old versions of this flyer");
  const vid = newId("v");
  const m = parsed.data;
  await sql(
    `insert into flyer_versions (id, flyer_id, parent_id, label, source, spec, thumb) values ($1, $2, $3, $4, $5, $6::jsonb, $7)`,
    [vid, id, m.parentId, m.label, m.source, JSON.stringify(m.spec), thumbBuf],
  );
  if (m.makeCurrent) await sql("update flyers set current_version_id = $2, updated_at = now() where id = $1", [id, vid]);
  const rows = await sql(`select ${VERSION_COLS} from flyer_versions where id = $1`, [vid]);
  return Response.json(mapVersion(rows[0]));
}
