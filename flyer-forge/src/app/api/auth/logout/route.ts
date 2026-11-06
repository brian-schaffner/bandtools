import { BASE_PATH } from "@/lib/base-path";
import { appOrigin, SESSION_COOKIE } from "@/lib/session";

export async function POST(req: Request) {
  if (req.headers.get("sec-fetch-site") === "cross-site") return Response.json({ error: "Cross-site requests are not allowed" }, { status: 403 });
  return new Response(null, {
    status: 303,
    headers: {
      location: `${appOrigin(req)}/signin?signedOut=1`,
      "set-cookie": `${SESSION_COOKIE}=; Path=${BASE_PATH || "/"}; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
      "cache-control": "no-store",
    },
  });
}
