import "server-only";
import { requireIdentity } from "../../cursor/identity";
import { sql } from "./db";
import { BANDTOOLS_SESSION_COOKIE, bandtoolsConfigured, readBandtoolsSession } from "./bandtools-auth";
import { authProvider, cookieFrom, googleConfig, readSession, SESSION_COOKIE } from "./session";

export interface Viewer {
  sub: string;
  email: string;
  name: string;
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Every API route starts here. On Cursor's hosting the caller must be a person the gate verified;
 * on Fly.io it must hold a signed Google session for an allowed email. Writes from another site
 * (a forged form post riding the viewer's session) are refused.
 */
export async function requireViewer(req: Request): Promise<Viewer | Response> {
  if (UNSAFE.has(req.method)) {
    if (req.headers.get("sec-fetch-site") === "cross-site") {
      return Response.json({ error: "Cross-site requests are not allowed" }, { status: 403 });
    }
  }
  if (authProvider() === "bandtools") {
    if (!bandtoolsConfigured()) return Response.json({ error: "Sign-in is not configured on this server" }, { status: 503 });
    const user = await readBandtoolsSession(cookieFrom(req.headers.get("cookie"), BANDTOOLS_SESSION_COOKIE));
    if (!user) return Response.json({ error: "Sign in to Band Tools to use this app" }, { status: 401 });
    return user;
  }
  if (authProvider() === "google") {
    const cfg = googleConfig();
    if (!cfg) return Response.json({ error: "Sign-in is not configured on this server" }, { status: 503 });
    const session = await readSession(cookieFrom(req.headers.get("cookie"), SESSION_COOKIE), cfg);
    if (!session) return Response.json({ error: "Sign in to use this app" }, { status: 401 });
    return { sub: `google:${session.sub}`, email: session.email, name: session.name };
  }
  const identity = await requireIdentity(req);
  if (identity instanceof Response) return identity;
  if (identity.kind !== "person") return Response.json({ error: "Sign in to use this app" }, { status: 403 });
  return { sub: identity.sub, email: identity.email, name: identity.name };
}

type Limit = { perHour: number; perDay: number };

export const QUOTAS = {
  ai: { perHour: 40, perDay: 200 },
  import: { perHour: 20, perDay: 60 },
} satisfies Record<string, Limit>;

/** Records one use of a costly action and refuses it once the viewer is over their hourly or daily allowance. */
export async function consumeQuota(viewer: Viewer, bucket: keyof typeof QUOTAS): Promise<Response | null> {
  const limit = QUOTAS[bucket];
  const rows = await sql<{ hour: string; day: string }>(
    `select count(*) filter (where created_at > now() - interval '1 hour') as hour,
            count(*) as day
     from usage_events where sub = $1 and bucket = $2 and created_at > now() - interval '1 day'`,
    [viewer.sub, bucket],
  );
  const hour = Number(rows[0]?.hour ?? 0);
  const day = Number(rows[0]?.day ?? 0);
  if (hour >= limit.perHour || day >= limit.perDay) {
    return Response.json(
      { error: hour >= limit.perHour ? "You've hit the hourly limit for this. Try again later." : "You've hit today's limit for this. Try again tomorrow." },
      { status: 429, headers: { "retry-after": hour >= limit.perHour ? "3600" : "86400" } },
    );
  }
  await sql("insert into usage_events (sub, bucket) values ($1, $2)", [viewer.sub, bucket]);
  if (Math.random() < 0.02) await sql("delete from usage_events where created_at < now() - interval '2 days'");
  return null;
}

/** Hard caps that keep the shared database from growing without bound. */
export const STORAGE = {
  assetBytesTotal: 2 * 1024 * 1024 * 1024,
  assetsTotal: 600,
  versionsPerFlyer: 400,
  flyersTotal: 1000,
  eventsTotal: 3000,
  setlistsTotal: 3000,
};

export async function countRows(table: "flyers" | "events" | "setlists" | "assets") {
  const rows = await sql<{ n: string }>(`select count(*) as n from ${table}`);
  return Number(rows[0]?.n ?? 0);
}

export function tooMany(what: string) {
  return Response.json({ error: `Storage limit reached: delete some ${what} first.` }, { status: 507 });
}

const SIGNATURES: [string, number[]][] = [
  ["image/jpeg", [0xff, 0xd8, 0xff]],
  ["image/png", [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]],
];

/** The real raster type of a stored preview or thumbnail, from its bytes, never from what the browser claimed. */
export function sniffRaster(buf: Buffer): "image/jpeg" | "image/png" | "image/webp" | null {
  for (const [mime, sig] of SIGNATURES) if (sig.every((b, i) => buf[i] === b)) return mime as "image/jpeg" | "image/png";
  if (buf.subarray(0, 4).toString("latin1") === "RIFF" && buf.subarray(8, 12).toString("latin1") === "WEBP") return "image/webp";
  return null;
}

export const SAFE_IMAGE_HEADERS = {
  "x-content-type-options": "nosniff",
  "content-security-policy": "default-src 'none'; sandbox",
};
