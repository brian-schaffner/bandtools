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
  homeAddress: z.string().max(300).optional(),
  noTrailerVenues: z.array(z.string().trim().max(160)).max(50).optional(),
});

export async function PUT(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Band name is required");
  const { name, genre, hometown } = parsed.data;
  const current = await getBand();
  const homeAddress = (parsed.data.homeAddress ?? current.homeAddress ?? "").trim();
  const noTrailer = (parsed.data.noTrailerVenues ?? current.noTrailerVenues ?? []).filter(Boolean);
  await sql(
    `insert into band (id, name, genre, hometown, home_address, no_trailer_venues, updated_at) values (1, $1, $2, $3, $4, $5::jsonb, now())
     on conflict (id) do update set name = $1, genre = $2, hometown = $3, home_address = $4, no_trailer_venues = $5::jsonb, updated_at = now()`,
    [name.trim(), genre.trim(), hometown.trim(), homeAddress, JSON.stringify(noTrailer)],
  );
  return Response.json(await getBand());
}
