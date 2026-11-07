import { sql, toBuffer } from "@/lib/db";
import { getAsset, jsonError } from "@/lib/repo";
import { requireViewer, SAFE_IMAGE_HEADERS } from "@/lib/guard";

const CHUNK_MAX = 3 * 1024 * 1024;

export async function GET(req: Request, ctx: RouteContext<"/api/assets/[id]/chunks/[idx]">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id, idx } = await ctx.params;
  const rows = await sql<{ data: unknown }>("select data from asset_chunks where asset_id = $1 and idx = $2", [id, Number(idx)]);
  if (!rows[0]) return jsonError("Not found", 404);
  const buf = toBuffer(rows[0].data);
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
  await sql(
    "insert into asset_chunks (asset_id, idx, data) values ($1, $2, $3) on conflict (asset_id, idx) do update set data = $3",
    [id, n, buf],
  );
  return Response.json({ ok: true });
}
