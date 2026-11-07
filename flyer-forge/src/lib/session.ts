/**
 * Google sign-in for hosts without Cursor's gate (Fly.io). Sessions are HMAC-signed cookies;
 * nothing is stored server-side. Runs in route handlers and in proxy.ts, so only WebCrypto is used.
 */

import { BASE_PATH } from "./base-path";

export const SESSION_COOKIE = "gfs_session";
export const STATE_COOKIE = "gfs_oauth_state";
export const SESSION_DAYS = 30;

export type AuthProvider = "cursor" | "google" | "bandtools";

export function authProvider(): AuthProvider {
  if (process.env.AUTH_PROVIDER === "bandtools") return "bandtools";
  if (process.env.AUTH_PROVIDER === "google" || process.env.FLY_APP_NAME) return "google";
  return "cursor";
}

export interface GoogleConfig {
  clientId: string;
  clientSecret: string;
  secret: string;
  allowed: string[];
}

/** Null when any required setting is missing; callers must then refuse every request. */
export function googleConfig(): GoogleConfig | null {
  const clientId = process.env.GOOGLE_CLIENT_ID?.trim() ?? "";
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET?.trim() ?? "";
  const secret = process.env.AUTH_SECRET?.trim() ?? "";
  const allowed = (process.env.ALLOWED_EMAILS ?? "")
    .split(/[,\s]+/)
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
  if (!clientId || !clientSecret || secret.length < 32 || !allowed.length) return null;
  return { clientId, clientSecret, secret, allowed };
}

export interface Session {
  sub: string;
  email: string;
  name: string;
  exp: number;
}

const enc = new TextEncoder();

function b64url(bytes: Uint8Array) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64urlDecode(s: string) {
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function hmac(secret: string, data: string) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

function safeEqual(a: Uint8Array, b: Uint8Array) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export async function signSession(s: Session, secret: string) {
  const body = b64url(enc.encode(JSON.stringify(s)));
  return `${body}.${b64url(await hmac(secret, body))}`;
}

export async function readSession(cookieValue: string | undefined | null, cfg: GoogleConfig): Promise<Session | null> {
  if (!cookieValue) return null;
  const [body, sig] = cookieValue.split(".");
  if (!body || !sig) return null;
  try {
    if (!safeEqual(b64urlDecode(sig), await hmac(cfg.secret, body))) return null;
    const s = JSON.parse(new TextDecoder().decode(b64urlDecode(body))) as Session;
    if (typeof s.exp !== "number" || s.exp * 1000 < Date.now()) return null;
    if (!cfg.allowed.includes(String(s.email).toLowerCase())) return null;
    return s;
  } catch {
    return null;
  }
}

export function cookieFrom(header: string | null, name: string) {
  if (!header) return null;
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return decodeURIComponent(part.slice(i + 1).trim());
  }
  return null;
}

export function safeNext(next: string | null | undefined) {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : "/calendar";
}

export function publicOrigin(req: Request) {
  const configured = process.env.APP_URL?.trim().replace(/\/$/, "");
  if (configured) return configured;
  const url = new URL(req.url);
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? url.host;
  const proto = req.headers.get("x-forwarded-proto") ?? url.protocol.replace(":", "");
  return `${proto}://${host}`;
}

/** Public URL of the app root, including the base path it is mounted under. */
export function appOrigin(req: Request) {
  return `${publicOrigin(req)}${BASE_PATH}`;
}

export const AUTH_COOKIE_PATH = `${BASE_PATH}/api/auth`;
