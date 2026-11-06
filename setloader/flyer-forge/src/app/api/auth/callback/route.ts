import { b64urlDecode, cookieFrom, googleConfig, publicOrigin, safeNext, SESSION_COOKIE, SESSION_DAYS, signSession, STATE_COOKIE, withBase } from "@/lib/session";

const clearState = `${STATE_COOKIE}=; Path=${withBase("/api/auth")}; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;

function fail(req: Request, code: string) {
  return new Response(null, {
    status: 303,
    headers: { location: `${publicOrigin(req)}${withBase("/signin")}?error=${code}`, "set-cookie": clearState, "cache-control": "no-store" },
  });
}

export async function GET(req: Request) {
  const cfg = googleConfig();
  if (!cfg) return fail(req, "not-configured");
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const [expected, next] = (cookieFrom(req.headers.get("cookie"), STATE_COOKIE) ?? "").split("|");
  if (!code || !expected || url.searchParams.get("state") !== expected) return fail(req, "state");

  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: cfg.clientId,
      client_secret: cfg.clientSecret,
      redirect_uri: `${publicOrigin(req)}${withBase("/api/auth/callback")}`,
      grant_type: "authorization_code",
    }),
  });
  if (!tokenRes.ok) return fail(req, "google");
  const { id_token } = (await tokenRes.json()) as { id_token?: string };
  if (!id_token) return fail(req, "google");

  // The ID token came straight from Google's token endpoint over TLS, so its claims are trusted (OIDC core 3.1.3.7).
  let claims: { iss?: string; aud?: string; sub?: string; email?: string; email_verified?: boolean; name?: string; exp?: number };
  try {
    claims = JSON.parse(new TextDecoder().decode(b64urlDecode(id_token.split(".")[1] ?? "")));
  } catch {
    return fail(req, "google");
  }
  const email = String(claims.email ?? "").toLowerCase();
  if (
    claims.aud !== cfg.clientId ||
    !["accounts.google.com", "https://accounts.google.com"].includes(String(claims.iss)) ||
    !claims.sub ||
    !claims.email_verified ||
    (claims.exp ?? 0) * 1000 < Date.now()
  )
    return fail(req, "google");
  if (!cfg.allowed.includes(email)) return fail(req, "not-allowed");

  const session = await signSession({ sub: claims.sub, email, name: claims.name ?? email, exp: Math.floor(Date.now() / 1000) + SESSION_DAYS * 86400 }, cfg.secret);
  const headers = new Headers({ location: `${publicOrigin(req)}${safeNext(next)}`, "cache-control": "no-store" });
  headers.append("set-cookie", `${SESSION_COOKIE}=${encodeURIComponent(session)}; Path=${withBase("/")}; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_DAYS * 86400}`);
  headers.append("set-cookie", clearState);
  return new Response(null, { status: 303, headers });
}
