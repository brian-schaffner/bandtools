import { publicOrigin, SESSION_COOKIE, withBase } from "@/lib/session";

export async function POST(req: Request) {
  if (req.headers.get("sec-fetch-site") === "cross-site") return Response.json({ error: "Cross-site requests are not allowed" }, { status: 403 });
  return new Response(null, {
    status: 303,
    headers: {
      location: `${publicOrigin(req)}${withBase("/signin")}?signedOut=1`,
      "set-cookie": `${SESSION_COOKIE}=; Path=${withBase("/")}; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
      "cache-control": "no-store",
    },
  });
}
