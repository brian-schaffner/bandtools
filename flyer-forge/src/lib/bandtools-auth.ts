/**
 * Sign-in when Flyer Forge runs inside the Band Tools container: the hub's Google sign-in leaves a
 * site-wide `session_token` cookie, and the Setlist Loader API says whose session it is.
 * Runs in route handlers and in proxy.ts.
 */

export const BANDTOOLS_SESSION_COOKIE = "session_token";

export interface BandtoolsUser {
  sub: string;
  email: string;
  name: string;
}

const OK_TTL_MS = 60_000;
const MISS_TTL_MS = 10_000;
const MAX_ENTRIES = 500;
const cache = new Map<string, { user: BandtoolsUser | null; at: number }>();

function statusUrl() {
  return `${(process.env.SETLOADER_INTERNAL_URL ?? "http://127.0.0.1:8002").replace(/\/+$/, "")}/user/status`;
}

/** Must equal the Setlist Loader's SECRET (NEXT_PUBLIC_* names would be frozen at build time). */
function apiSecret() {
  return process.env.SETLOADER_SECRET || process.env.SECRET || "";
}

/** Empty means every signed-in Band Tools user may use the app. */
function allowedEmails() {
  return (process.env.ALLOWED_EMAILS ?? "")
    .split(/[,\s]+/)
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

export function bandtoolsConfigured() {
  return apiSecret() !== "";
}

export async function readBandtoolsSession(token: string | null | undefined): Promise<BandtoolsUser | null> {
  if (!token || token === "guest-session" || !bandtoolsConfigured()) return null;
  const hit = cache.get(token);
  if (hit && Date.now() - hit.at < (hit.user ? OK_TTL_MS : MISS_TTL_MS)) return hit.user;

  let user: BandtoolsUser | null = null;
  try {
    const res = await fetch(statusUrl(), {
      headers: { "X-Secret": apiSecret(), "X-Session-ID": token },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (res.ok) {
      const data = (await res.json()) as { authenticated?: boolean; user_id?: unknown; user_email?: unknown };
      const email = String(data.user_email ?? "").trim();
      const allowed = allowedEmails();
      if (data.authenticated && email && (!allowed.length || allowed.includes(email.toLowerCase()))) {
        user = { sub: `bandtools:${String(data.user_id ?? email)}`, email, name: email.split("@")[0] };
      }
    }
  } catch {
    return null;
  }
  if (cache.size >= MAX_ENTRIES) cache.clear();
  cache.set(token, { user, at: Date.now() });
  return user;
}
