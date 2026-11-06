import { sql, toBuffer } from "@/lib/db";
import { jsonError } from "@/lib/repo";
import { requireViewer, SAFE_IMAGE_HEADERS, sniffRaster } from "@/lib/guard";

export async function GET(req: Request, ctx: RouteContext<"/api/assets/[id]/preview">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const rows = await sql<{ preview: unknown; preview_mime: string | null }>(
    "select preview, preview_mime from assets where id = $1",
    [id],
  );
  if (!rows[0]?.preview) return jsonError("Not found", 404);
  const buf = toBuffer(rows[0].preview);
  const mime = sniffRaster(buf);
  if (!mime) return jsonError("Not found", 404);
  return new Response(new Uint8Array(buf), {
    headers: {
      ...SAFE_IMAGE_HEADERS,
      "content-type": mime,
      "cache-control": "private, max-age=31536000, immutable",
    },
  });
}
