"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarDays, ListMusic, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SetlistLoader } from "./setlist-loader";
import { useFetch } from "@/hooks/use-fetch";
import { eventLabel, formatDuration, totalDuration, type Setlist, type SongStat } from "@/lib/events";

export function SetlistsView() {
  const router = useRouter();
  const lists = useFetch<Setlist[]>("/api/setlists");
  const songs = useFetch<Record<string, SongStat>>("/api/songs");
  const [open, setOpen] = useState(false);
  const top = Object.values(songs.data ?? {})
    .sort((a, b) => b.count - a.count || (b.lastDate ?? "").localeCompare(a.lastDate ?? ""))
    .slice(0, 15);

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-8 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Set lists</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">Every set list, filed under the gig it was played at. Load one from the gig page to file it automatically.</p>
        </div>
        <Button size="lg" onClick={() => setOpen(true)}>
          <Plus /> Load set list
        </Button>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section>
          {lists.loading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : lists.error ? (
            <div className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
              {lists.error}{" "}
              <Button variant="link" onClick={lists.reload}>
                Retry
              </Button>
            </div>
          ) : !lists.data?.length ? (
            <div className="grid place-items-center rounded-lg border border-dashed border-border px-6 py-20 text-center">
              <div className="max-w-sm space-y-3">
                <ListMusic className="mx-auto size-6 text-muted-foreground" />
                <h2 className="text-lg font-medium">No set lists yet</h2>
                <p className="text-sm text-muted-foreground">Paste the list you already use, upload a .txt or .csv, then attach it to a gig on the calendar.</p>
                <Button onClick={() => setOpen(true)}>Load your first set list</Button>
              </div>
            </div>
          ) : (
            <ul className="space-y-2">
              {lists.data.map((s) => {
                const t = totalDuration(s.items);
                return (
                  <li key={s.id}>
                    <Link href={`/setlists/${s.id}`} className="flex items-center gap-4 rounded-md border border-border/60 bg-card/40 p-3 transition-colors hover:border-foreground/40">
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">{s.name}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
                          <span>
                            {t.songs} songs{t.seconds ? ` · ${formatDuration(t.seconds)}` : ""}
                          </span>
                          {s.event ? (
                            <span className="flex items-center gap-1">
                              <CalendarDays className="size-3" /> {s.event.date} · {eventLabel(s.event)}
                            </span>
                          ) : (
                            <span className="text-amber-300/80">Not filed under a gig</span>
                          )}
                        </div>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <aside>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">Most played</h2>
          {songs.loading ? (
            <Skeleton className="h-64" />
          ) : !top.length ? (
            <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">Song counts build up as set lists are filed under gigs that have happened.</p>
          ) : (
            <ol className="rounded-md border border-border/60 bg-card/40 p-2 text-sm">
              {top.map((s, i) => (
                <li key={s.title} className="flex items-baseline gap-2 px-1 py-1">
                  <span className="w-5 text-right font-mono text-xs text-muted-foreground">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate">{s.title}</span>
                  <span className="font-mono text-xs tabular-nums">{s.count}×</span>
                  <span className="w-20 text-right text-xs text-muted-foreground">{s.lastDate}</span>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>

      <SetlistLoader open={open} onOpenChange={setOpen} eventId={null} defaultName="New set list" onCreated={(s) => router.push(`/setlists/${s.id}`)} />
    </div>
  );
}
