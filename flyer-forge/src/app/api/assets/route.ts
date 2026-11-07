import { z } from "zod";
import { deleteAssets } from "@/lib/chunk-store";
import { sql } from "@/lib/db";
import { getAsset, jsonError, listAssets, newId } from "@/lib/repo";
import { requireViewer, sniffRaster, STORAGE, tooMany } from "@/lib/guard";

const MAX_BYTES = 60 * 1024 * 1024;
const MIME = ["image/png", "image/jpeg", "image/webp", "image/svg+xml"];

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const kind = new URL(req.url).searchParams.get("kind") ?? undefined;
  return Response.json(await listAssets(kind));
}

const Meta = z.object({
  kind: z.enum(["logo", "photo", "reference"]),
  name: z.string().max(160).default(""),
  photoKind: z.enum(["group", "individual", "live", "other"]).nullable().optional(),
  memberIds: z.array(z.string()).default([]),
  credit: z.string().max(160).default(""),
  mime: z.string(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  byteSize: z.number().int().positive().max(MAX_BYTES),
  sha256: z.string().regex(/^[0-9a-f]{64}$/),
  chunkCount: z.number().int().positive().max(64),
});

const CHUNK_SIZE = 3 * 1024 * 1024;

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const form = await req.formData().catch(() => null);
  if (!form) return jsonError("Expected a multipart upload");
  const parsed = Meta.safeParse(JSON.parse(String(form.get("meta") ?? "null")));
  if (!parsed.success) return jsonError("Upload details were invalid or the file is larger than 60 MB");
  const m = parsed.data;
  if (!MIME.includes(m.mime)) return jsonError("Use PNG, JPEG, WebP or SVG files");
  if (m.chunkCount !== Math.ceil(m.byteSize / CHUNK_SIZE)) return jsonError("Upload parts don't match the file size");
  await deleteAssets("not complete and created_at < now() - interval '1 day'");
  const usage = await sql<{ n: string; bytes: string | null }>("select count(*) as n, sum(byte_size) as bytes from assets");
  if (Number(usage[0]?.n ?? 0) >= STORAGE.assetsTotal || Number(usage[0]?.bytes ?? 0) + m.byteSize > STORAGE.assetBytesTotal) return tooMany("photos, logos or references");
  const preview = form.get("preview");
  const previewBuf = preview instanceof Blob ? Buffer.from(await preview.arrayBuffer()) : null;
  if (previewBuf && previewBuf.byteLength > 2 * 1024 * 1024) return jsonError("Preview too large");
  const previewMime = previewBuf ? sniffRaster(previewBuf) : null;
  if (previewBuf && !previewMime) return jsonError("Preview must be a JPEG, PNG or WebP image");
  const id = newId(m.kind === "logo" ? "logo" : m.kind === "photo" ? "photo" : "ref");
  await sql(
    `insert into assets (id, kind, name, photo_kind, member_ids, mime, width, height, byte_size, sha256, chunk_count, credit, preview, preview_mime)
     values ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11, $12, $13, $14)`,
    [
      id,
      m.kind,
      m.name.trim(),
      m.kind === "photo" ? (m.photoKind ?? "group") : null,
      JSON.stringify(m.memberIds),
      m.mime,
      m.width,
      m.height,
      m.byteSize,
      m.sha256,
      m.chunkCount,
      m.credit.trim(),
      previewBuf,
      previewMime,
    ],
  );
  return Response.json(await getAsset(id));
}
