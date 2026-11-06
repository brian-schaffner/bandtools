import { connection } from "next/server";
import { AI_MODEL, aiEnabled } from "@/lib/ai";
import { requireViewer } from "@/lib/guard";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  await connection();
  return Response.json({ enabled: aiEnabled(), model: AI_MODEL });
}
