import { NextResponse, type NextRequest } from "next/server";
import { authProvider, googleConfig, readSession, SESSION_COOKIE, stripBasePath, withBase } from "@/lib/session";

/** On Fly.io every page and API call needs a Google session; API routes also re-check it themselves. */
export async function proxy(request: NextRequest) {
  if (authProvider() !== "google") return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  const pathNoBase = stripBasePath(pathname);
  if (pathNoBase === "/signin" || pathNoBase.startsWith("/api/auth/")) return NextResponse.next();
  const cfg = googleConfig();
  const session = cfg ? await readSession(request.cookies.get(SESSION_COOKIE)?.value, cfg) : null;
  if (session) return NextResponse.next();
  if (pathNoBase.startsWith("/api/")) return NextResponse.json({ error: cfg ? "Sign in to use this app" : "Sign-in is not configured on this server" }, { status: cfg ? 401 : 503 });
  const url = request.nextUrl.clone();
  url.pathname = withBase("/signin");
  url.search = `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
