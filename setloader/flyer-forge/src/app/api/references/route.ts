import { connection } from "next/server";
import { z } from "zod";
import { sql } from "@/lib/db";
import { jsonError, listRefs, mapRef, newId } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  return Response.json(await listRefs());
}

const RefBody = z.object({
  kind: z.enum(["avoid", "inspire"]),
  title: z.string().trim().min(1).max(160),
  notes: z.string().max(4000).default(""),
  traits: z.array(z.string().trim().min(1).max(240)).max(30).default([]),
  recipeId: z.string().nullable().default(null),
  imageAssetId: z.string().nullable().default(null),
});

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = RefBody.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("A title is required");
  const r = parsed.data;
  const id = newId("sref");
  const rows = await sql(
    `insert into style_refs (id, kind, title, notes, traits, recipe_id, image_asset_id)
     values ($1, $2, $3, $4, $5::jsonb, $6, $7) returning *`,
    [id, r.kind, r.title, r.notes, JSON.stringify(r.traits), r.recipeId, r.imageAssetId],
  );
  return Response.json(mapRef(rows[0]));
}
