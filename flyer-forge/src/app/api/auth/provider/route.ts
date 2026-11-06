import { authProvider } from "@/lib/session";

/** Public: tells the sign-in page which sign-in to offer. */
export async function GET() {
  return Response.json({ provider: authProvider() }, { headers: { "cache-control": "no-store" } });
}
