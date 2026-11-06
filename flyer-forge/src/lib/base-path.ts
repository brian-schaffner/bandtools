/** The sub-path the app is mounted under (e.g. "/forge"), fixed at build time via FLYER_FORGE_BASE_PATH. */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/**
 * Prefix an app-absolute URL with the base path. next/link, router.push and redirect() add it
 * themselves; raw fetch(), <img src>, <a href>, <form action> and Location headers do not.
 */
export function withBase(path: string) {
  return path.startsWith("/") && !path.startsWith("//") ? `${BASE_PATH}${path}` : path;
}

/** The Band Tools hub (outside this app), where AUTH_PROVIDER=bandtools users sign in. */
export const BAND_TOOLS_HOME = process.env.NEXT_PUBLIC_BAND_TOOLS_HOME || "/";
