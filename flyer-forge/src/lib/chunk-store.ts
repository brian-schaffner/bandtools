import "server-only";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { sql, toBuffer } from "@/lib/db";

// PGlite keeps its whole heap in WebAssembly memory that never shrinks, so original upload bytes
// live on disk next to it; a single phone photo stored as bytea grew the server by ~700 MB.
// With a real Postgres (DATABASE_URL) and no ASSET_FILES_DIR, parts stay in the asset_chunks table.
const FILE_DIR = process.env.ASSET_FILES_DIR?.trim() || (process.env.DATABASE_URL?.trim() ? "" : ".data/assets");
const SAFE_ID = /^[a-z]+_[0-9a-f]{16}$/;

function partPath(assetId: string, idx: number) {
  if (!SAFE_ID.test(assetId) || !Number.isInteger(idx) || idx < 0) throw new Error("Bad asset part");
  return path.join(FILE_DIR, assetId, String(idx));
}

export async function putChunk(assetId: string, idx: number, data: Buffer): Promise<void> {
  if (!FILE_DIR) {
    await sql(
      "insert into asset_chunks (asset_id, idx, data) values ($1, $2, $3) on conflict (asset_id, idx) do update set data = $3",
      [assetId, idx, data],
    );
    return;
  }
  const file = partPath(assetId, idx);
  await mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmp, data);
  await rename(tmp, file);
}

/** Reads a part from disk, falling back to asset_chunks for files uploaded before parts moved to disk. */
export async function getChunk(assetId: string, idx: number): Promise<Buffer | null> {
  if (FILE_DIR && SAFE_ID.test(assetId)) {
    try {
      return await readFile(partPath(assetId, idx));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
  }
  const rows = await sql<{ data: unknown }>("select data from asset_chunks where asset_id = $1 and idx = $2", [assetId, idx]);
  return rows[0] ? toBuffer(rows[0].data) : null;
}

/** Deletes asset rows (parts in asset_chunks cascade) and their files on disk. */
export async function deleteAssets(where: string, params: unknown[] = []): Promise<void> {
  const rows = await sql<{ id: string }>(`delete from assets where ${where} returning id`, params);
  if (!FILE_DIR) return;
  await Promise.all(
    rows.filter((r) => SAFE_ID.test(r.id)).map((r) => rm(path.join(FILE_DIR, r.id), { recursive: true, force: true })),
  );
}
