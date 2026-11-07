import { getChunk, putChunk } from "@/lib/chunk-store";
import { getAsset, jsonError } from "@/lib/repo";
import { requireViewer, SAFE_IMAGE_HEADERS } from "@/lib/guard";

const CHUNK_MAX = 3 * 1024 * 1024;

export async function GET(req: Request, ctx: RouteContext<"/api/assets/[id]/chunks/[idx]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id, idx } = await ctx.params;
  const n = Number(idx);
  if (!Number.isInteger(n) || n < 0) return jsonError("Not found", 404);
  const buf = await getChunk(id, n);
  if (!buf) return jsonError("Not found", 404);
  return new Response(new Uint8Array(buf), {
    headers: {
      ...SAFE_IMAGE_HEADERS,
      "content-type": "application/octet-stream",
      "content-disposition": "attachment",
      "cache-control": "private, max-age=31536000, immutable",
    },
  });
}

export async function PUT(req: Request, ctx: RouteContext<"/api/assets/[id]/chunks/[idx]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id, idx } = await ctx.params;
  const n = Number(idx);
  const asset = await getAsset(id);
  if (!asset) return jsonError("Not found", 404);
  if (asset.complete) return jsonError("Originals are immutable once uploaded", 409);
  if (!Number.isInteger(n) || n < 0 || n >= asset.chunkCount) return jsonError("Bad part index");
  const buf = Buffer.from(await req.arrayBuffer());
  if (buf.byteLength === 0 || buf.byteLength > CHUNK_MAX) return jsonError("Bad part size");
  await putChunk(id, n, buf);
  return Response.json({ ok: true });
}
