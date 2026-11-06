import { appOrigin, AUTH_COOKIE_PATH, googleConfig, safeNext, STATE_COOKIE } from "@/lib/session";

export async function GET(req: Request) {
  const cfg = googleConfig();
  if (!cfg) return Response.redirect(`${appOrigin(req)}/signin?error=not-configured`, 303);
  const state = crypto.randomUUID();
  const next = safeNext(new URL(req.url).searchParams.get("next"));
  const params = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: `${appOrigin(req)}/api/auth/callback`,
    response_type: "code",
    scope: "openid email profile",
    state,
    prompt: "select_account",
  });
  return new Response(null, {
    status: 303,
    headers: {
      location: `https://accounts.google.com/o/oauth2/v2/auth?${params}`,
      "set-cookie": `${STATE_COOKIE}=${encodeURIComponent(`${state}|${next}`)}; Path=${AUTH_COOKIE_PATH}; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
      "cache-control": "no-store",
    },
  });
}
