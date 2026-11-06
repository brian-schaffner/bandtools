import { sql, toBuffer } from "@/lib/db";
import { jsonError } from "@/lib/repo";
import { requireViewer, SAFE_IMAGE_HEADERS, sniffRaster } from "@/lib/guard";

export async function GET(req: Request, ctx: RouteContext<"/api/flyers/[id]/versions/[vid]/thumb">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id, vid } = await ctx.params;
  const rows = await sql<{ thumb: unknown }>("select thumb from flyer_versions where id = $1 and flyer_id = $2", [vid, id]);
  if (!rows[0]?.thumb) return jsonError("Not found", 404);
  const buf = toBuffer(rows[0].thumb);
  const mime = sniffRaster(buf);
  if (!mime) return jsonError("Not found", 404);
  return new Response(new Uint8Array(buf), {
    headers: { ...SAFE_IMAGE_HEADERS, "content-type": mime, "cache-control": "private, max-age=31536000, immutable" },
  });
}
