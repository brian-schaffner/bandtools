import { connection } from "next/server";
import { z } from "zod";
import { sql } from "@/lib/db";
import { getBand, jsonError, listMembers } from "@/lib/repo";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  const [band, members] = await Promise.all([getBand(), listMembers()]);
  return Response.json({ band, members });
}

const Body = z.object({
  name: z.string().max(120),
  genre: z.string().max(120).default(""),
  hometown: z.string().max(120).default(""),
});

export async function PUT(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Band name is required");
  const { name, genre, hometown } = parsed.data;
  await sql(
    `insert into band (id, name, genre, hometown, updated_at) values (1, $1, $2, $3, now())
     on conflict (id) do update set name = $1, genre = $2, hometown = $3, updated_at = now()`,
    [name.trim(), genre.trim(), hometown.trim()],
  );
  return Response.json(await getBand());
}
