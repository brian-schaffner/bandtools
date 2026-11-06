import "server-only";
import { mkdir, readdir, readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";
import pg from "pg";

const databaseUrl = process.env.DATABASE_URL?.trim() ?? "";
let pool: pg.Pool | undefined;
let local: Promise<PGlite> | undefined;

// Locally the database persists under .data/ so uploads survive dev-server restarts.
const LOCAL_DIR = process.env.LOCAL_PGLITE_DIR ?? ".data/pglite";

export async function sql<T = Record<string, unknown>>(text: string, params: unknown[] = []): Promise<T[]> {
  if (databaseUrl !== "") {
    pool ??= new pg.Pool({ connectionString: databaseUrl, max: 5 });
    return (await pool.query(text, params)).rows as T[];
  }
  local ??= startLocal().catch((error: unknown) => {
    local = undefined;
    throw error;
  });
  return (await (await local).query<T>(text, params)).rows;
}

async function startLocal(): Promise<PGlite> {
  await mkdir(LOCAL_DIR, { recursive: true });
  const db = new PGlite(LOCAL_DIR);
  await db.exec(
    "create table if not exists schema_migrations (name text primary key, applied_at timestamptz not null default now())",
  );
  const done = new Set(
    (await db.query<{ name: string }>("select name from schema_migrations")).rows.map((r) => r.name),
  );
  const files = (await readdir("migrations").catch(() => [])).filter((f) => f.endsWith(".sql")).sort();
  for (const file of files.filter((f) => !done.has(f))) {
    await db.transaction(async (tx) => {
      await tx.exec(await readFile(`migrations/${file}`, "utf8"));
      await tx.query("insert into schema_migrations (name) values ($1)", [file]);
    });
  }
  return db;
}

export function toBuffer(value: unknown): Buffer {
  if (Buffer.isBuffer(value)) return value;
  if (value instanceof Uint8Array) return Buffer.from(value.buffer, value.byteOffset, value.byteLength);
  throw new Error("Expected binary column");
}
