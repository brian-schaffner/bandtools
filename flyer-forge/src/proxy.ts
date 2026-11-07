import { NextResponse, type NextRequest } from "next/server";
import { BANDTOOLS_SESSION_COOKIE, bandtoolsConfigured, readBandtoolsSession } from "@/lib/bandtools-auth";
import { authProvider, googleConfig, readSession, SESSION_COOKIE } from "@/lib/session";

/** On Fly.io every page and API call needs a session; API routes also re-check it themselves. */
export async function proxy(request: NextRequest) {
  const provider = authProvider();
  if (provider === "cursor") return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  if (pathname === "/signin" || pathname.startsWith("/api/auth/")) return NextResponse.next();
  let configured: boolean;
  let signedIn: boolean;
  if (provider === "bandtools") {
    configured = bandtoolsConfigured();
    signedIn = configured && !!(await readBandtoolsSession(request.cookies.get(BANDTOOLS_SESSION_COOKIE)?.value));
  } else {
    const cfg = googleConfig();
    configured = !!cfg;
    signedIn = !!cfg && !!(await readSession(request.cookies.get(SESSION_COOKIE)?.value, cfg));
  }
  if (signedIn) return NextResponse.next();
  if (pathname.startsWith("/api/")) return NextResponse.json({ error: configured ? "Sign in to use this app" : "Sign-in is not configured on this server" }, { status: configured ? 401 : 503 });
  const url = request.nextUrl.clone();
  url.pathname = "/signin";
  url.search = `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // "/" is listed on its own because under a basePath the catch-all no longer matches the bare root.
  matcher: ["/", "/((?!_next/static|_next/image|favicon.ico).*)"],
};
