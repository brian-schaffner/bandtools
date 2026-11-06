import { googleConfig, publicOrigin, safeNextInner, STATE_COOKIE, withBase } from "@/lib/session";

export async function GET(req: Request) {
  const cfg = googleConfig();
  if (!cfg) return Response.redirect(new URL(`${withBase("/signin")}?error=not-configured`, publicOrigin(req)), 303);
  const state = crypto.randomUUID();
  const next = safeNextInner(new URL(req.url).searchParams.get("next"));
  const params = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: `${publicOrigin(req)}${withBase("/api/auth/callback")}`,
    response_type: "code",
    scope: "openid email profile",
    state,
    prompt: "select_account",
  });
  return new Response(null, {
    status: 303,
    headers: {
      location: `https://accounts.google.com/o/oauth2/v2/auth?${params}`,
      "set-cookie": `${STATE_COOKIE}=${encodeURIComponent(`${state}|${next}`)}; Path=${withBase("/api/auth")}; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
      "cache-control": "no-store",
    },
  });
}
