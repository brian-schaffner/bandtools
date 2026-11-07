"use client";

import { useSearchParams } from "next/navigation";
import { buttonVariants } from "@/components/ui/button";
import { useFetch } from "@/hooks/use-fetch";
import { BAND_TOOLS_HOME, withBase } from "@/lib/base-path";
import { safeNext } from "@/lib/session";

const ERRORS: Record<string, string> = {
  "not-allowed": "That Google account isn't on this band's list. Ask whoever runs the app to add your email.",
  "not-configured": "Sign-in isn't set up on this server yet.",
  state: "The sign-in link expired. Try again.",
  google: "Google didn't confirm the sign-in. Try again.",
};

export function SigninView() {
  const params = useSearchParams();
  const error = params.get("error");
  const next = params.get("next") ?? "/calendar";
  const provider = useFetch<{ provider: "cursor" | "google" | "bandtools" }>("/api/auth/provider");
  const bandtools = provider.data?.provider === "bandtools";
  return (
    <div className="grid flex-1 place-items-center px-6 py-20">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-border/60 bg-card/40 p-8 text-center">
        <span className="mx-auto grid size-10 place-items-center rounded-md bg-[#E4572E] font-mono text-sm font-bold text-[#111]">GF</span>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {bandtools
              ? "Sign in with Google on the Band Tools home page, then come back here."
              : "Gig calendar, flyers and set lists for the band. Members only."}
          </p>
        </div>
        {error && <p className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">{ERRORS[error] ?? "Sign-in failed. Try again."}</p>}
        {params.get("signedOut") && !error && <p className="text-sm text-muted-foreground">You&apos;re signed out.</p>}
        {provider.loading ? null : bandtools ? (
          <div className="space-y-2">
            <a href={BAND_TOOLS_HOME} className={buttonVariants({ size: "lg", className: "w-full" })}>
              Sign in on Band Tools
            </a>
            <a href={withBase(safeNext(next))} className={buttonVariants({ variant: "link", size: "sm" })}>
              I&apos;ve signed in, continue
            </a>
          </div>
        ) : (
          <a href={withBase(`/api/auth/google?next=${encodeURIComponent(next)}`)} className={buttonVariants({ size: "lg", className: "w-full" })}>
            Continue with Google
          </a>
        )}
      </div>
    </div>
  );
}
