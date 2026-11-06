import { requireViewer } from "@/lib/guard";
import { authProvider } from "@/lib/session";

export async function GET(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  return Response.json({ name: viewer.name, email: viewer.email, provider: authProvider() }, { headers: { "cache-control": "private, no-store" } });
}
