import { connection } from "next/server";
import { sql } from "@/lib/db";

/** Public liveness check for the deploy smoke test: process uptime, memory and whether the database answers. */
export async function GET() {
  await connection();
  const started = Date.now();
  let db: { ok: boolean; ms: number; error?: string };
  try {
    await sql("select count(*) from assets");
    db = { ok: true, ms: Date.now() - started };
  } catch (error) {
    db = { ok: false, ms: Date.now() - started, error: error instanceof Error ? error.message.slice(0, 200) : "unknown" };
  }
  const mem = process.memoryUsage();
  return Response.json(
    {
      ok: db.ok,
      uptimeSeconds: Math.round(process.uptime()),
      rssMB: Math.round(mem.rss / 1048576),
      db,
    },
    { status: db.ok ? 200 : 503, headers: { "cache-control": "no-store" } },
  );
}
