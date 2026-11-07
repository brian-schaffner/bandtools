import { connection } from "next/server";
import { authProvider } from "@/lib/session";

/** Public: tells the sign-in page which sign-in to offer. */
export async function GET() {
  // AUTH_PROVIDER is a runtime setting; without this the build prerenders the build machine's value.
  await connection();
  return Response.json({ provider: authProvider() }, { headers: { "cache-control": "no-store" } });
}
