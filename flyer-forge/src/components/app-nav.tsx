"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, LogOut } from "lucide-react";
import { useFetch } from "@/hooks/use-fetch";
import { cn } from "@/lib/utils";
import { BAND_TOOLS_HOME, withBase } from "@/lib/base-path";

const LINKS = [
  { href: "/calendar", label: "Calendar", match: (p: string) => p.startsWith("/calendar") || p.startsWith("/events") },
  { href: "/", label: "Flyers", match: (p: string) => p === "/" || p.startsWith("/flyers") },
  { href: "/setlists", label: "Set lists", match: (p: string) => p.startsWith("/setlists") },
  { href: "/kit", label: "Band kit", match: (p: string) => p.startsWith("/kit") },
  { href: "/references", label: "References", match: (p: string) => p.startsWith("/references") },
];

export function AppNav() {
  const pathname = usePathname() ?? "/";
  const signin = pathname === "/signin";
  const me = useFetch<{ name: string; email: string; provider: "cursor" | "google" | "bandtools" }>(signin ? null : "/api/auth/me");
  return (
    <header className="sticky top-0 z-40 border-b print:hidden border-border/60 bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1500px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid size-7 place-items-center rounded-sm bg-[#E4572E] font-mono text-xs font-bold text-[#111]">GF</span>
          <span className="hidden sm:inline">Gig Flyer Studio</span>
        </Link>
        {!signin && <nav className="-mx-1 flex items-center gap-1 overflow-x-auto px-1 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "shrink-0 rounded-md px-2.5 py-1.5 text-muted-foreground sm:px-3 transition-colors hover:text-foreground",
                l.match(pathname) && "bg-muted text-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>}
        {me.data?.provider === "google" && (
          <form action={withBase("/api/auth/logout")} method="post" className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden max-w-40 truncate md:inline">{me.data.name}</span>
            <button type="submit" className="flex items-center gap-1 rounded-md px-2 py-1.5 hover:bg-muted hover:text-foreground" aria-label="Sign out">
              <LogOut className="size-3.5" /> <span className="hidden sm:inline">Sign out</span>
            </button>
          </form>
        )}
        {me.data?.provider === "bandtools" && (
          <div className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden max-w-40 truncate md:inline">{me.data.email}</span>
            <a href={BAND_TOOLS_HOME} className="flex items-center gap-1 rounded-md px-2 py-1.5 hover:bg-muted hover:text-foreground">
              <LayoutGrid className="size-3.5" /> <span className="hidden sm:inline">Band Tools</span>
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
