import { createHash } from "node:crypto";
import { deleteAssets, getChunk } from "@/lib/chunk-store";
import { sql } from "@/lib/db";
import { getAsset, jsonError } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

/** Re-hashes the stored bytes server-side; the asset only becomes usable if they match the client's SHA-256. */
export async function POST(req: Request, ctx: RouteContext<"/api/assets/[id]/complete">) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const { id } = await ctx.params;
  const asset = await getAsset(id);
  if (!asset) return jsonError("Not found", 404);
  if (asset.complete) return Response.json(asset);
  const hash = createHash("sha256");
  let total = 0;
  for (let i = 0; i < asset.chunkCount; i++) {
    const buf = await getChunk(id, i);
    if (!buf) return jsonError(`Part ${i + 1} is missing; please re-upload`, 409);
    total += buf.byteLength;
    hash.update(buf);
  }
  const digest = hash.digest("hex");
  if (total !== asset.byteSize || digest !== asset.sha256) {
    await deleteAssets("id = $1", [id]);
    return jsonError("The stored file did not match the original byte-for-byte; upload discarded", 422);
  }
  await sql("update assets set complete = true where id = $1", [id]);
  return Response.json(await getAsset(id));
}
