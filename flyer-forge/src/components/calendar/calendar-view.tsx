"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { CalendarPlus, ChevronLeft, ChevronRight, Download, FileText, ListMusic, RefreshCw, Upload } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Choice, Field } from "@/components/fields";
import { useFetch } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import { eventLabel, isPast, statusLabel, todayIso, type CalendarEvent, type EventStatus } from "@/lib/events";
import { cn } from "@/lib/utils";
import { withBase } from "@/lib/base-path";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export function statusTone(e: { status: EventStatus; date: string }) {
  if (e.status === "cancelled") return "bg-muted text-muted-foreground line-through";
  if (isPast(e)) return "bg-secondary text-secondary-foreground";
  return e.status === "tentative" ? "border border-dashed border-amber-400/60 bg-amber-400/10 text-amber-200" : "bg-[#E4572E] text-[#111]";
}

export function DateBlock({ date, className }: { date: string; className?: string }) {
  const d = new Date(`${date}T12:00:00`);
  return (
    <div className={cn("grid w-14 shrink-0 place-items-center rounded-md border border-border/60 bg-card py-1.5 text-center leading-none", className)}>
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{MONTHS[d.getMonth()].slice(0, 3)}</span>
      <span className="mt-0.5 text-xl font-semibold tabular-nums">{d.getDate()}</span>
      <span className="mt-0.5 text-[10px] text-muted-foreground">{d.getFullYear() !== new Date().getFullYear() ? d.getFullYear() : DOW[d.getDay()]}</span>
    </div>
  );
}

function monthGrid(year: number, month: number) {
  const first = new Date(year, month, 1);
  const start = new Date(year, month, 1 - first.getDay());
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return { iso, day: d.getDate(), inMonth: d.getMonth() === month };
  });
}

export function CalendarView() {
  const events = useFetch<CalendarEvent[]>("/api/events");
  const now = new Date();
  const [cursor, setCursor] = useState({ y: now.getFullYear(), m: now.getMonth() });
  const [newDate, setNewDate] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const facebook = useFacebookSync(events.reload);

  const byDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const e of events.data ?? []) map.set(e.date, [...(map.get(e.date) ?? []), e]);
    return map;
  }, [events.data]);
  const today = todayIso();
  const upcoming = (events.data ?? []).filter((e) => e.date >= today);
  const history = (events.data ?? []).filter((e) => e.date < today).reverse();
  const cells = monthGrid(cursor.y, cursor.m);
  const shift = (n: number) => setCursor((c) => ({ y: c.y + Math.floor((c.m + n) / 12), m: (((c.m + n) % 12) + 12) % 12 }));

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-8 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Calendar</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Every gig in one place: venue, logistics schedule, flyers and set lists. Past shows stay here as your history.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {facebook.configured && (
            <Button variant="outline" onClick={() => void facebook.sync(false)} disabled={facebook.busy} title={facebook.lastSynced ? `Last synced ${facebook.lastSynced.toLocaleString()}` : undefined}>
              <RefreshCw className={cn(facebook.busy && "animate-spin")} /> {facebook.busy ? "Syncing…" : "Sync from Facebook"}
            </Button>
          )}
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload /> Import .ics
          </Button>
          <a href={withBase("/api/events/ics")} className={buttonVariants({ variant: "outline" })} download>
            <Download /> Export .ics
          </a>
          <Button size="lg" onClick={() => setNewDate(today)}>
            <CalendarPlus /> New gig
          </Button>
        </div>
      </div>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="rounded-lg border border-border/60 bg-card/40 p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-lg font-medium">
              {MONTHS[cursor.m]} {cursor.y}
            </h2>
            <div className="ml-auto flex items-center gap-1">
              <Button variant="ghost" size="icon-sm" onClick={() => shift(-1)} aria-label="Previous month">
                <ChevronLeft />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setCursor({ y: now.getFullYear(), m: now.getMonth() })}>
                Today
              </Button>
              <Button variant="ghost" size="icon-sm" onClick={() => shift(1)} aria-label="Next month">
                <ChevronRight />
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-md border border-border/60 bg-border/60 text-xs">
            {DOW.map((d) => (
              <div key={d} className="bg-card px-2 py-1.5 text-center font-medium text-muted-foreground">
                <span className="sm:hidden">{d[0]}</span>
                <span className="hidden sm:inline">{d}</span>
              </div>
            ))}
            {cells.map((c) => {
              const list = byDate.get(c.iso) ?? [];
              return (
                <div
                  key={c.iso}
                  role="button"
                  tabIndex={0}
                  onClick={() => (list.length ? null : setNewDate(c.iso))}
                  onKeyDown={(e) => e.key === "Enter" && !list.length && setNewDate(c.iso)}
                  className={cn(
                    "group min-h-14 bg-background p-1 text-left align-top transition-colors sm:min-h-24 sm:p-1.5",
                    !c.inMonth && "bg-background/40 text-muted-foreground/50",
                    !list.length && "cursor-pointer hover:bg-muted/40",
                  )}
                >
                  <div className={cn("mb-1 grid size-6 place-items-center rounded-full tabular-nums", c.iso === today && "bg-primary text-primary-foreground")}>{c.day}</div>
                  <div className="space-y-1">
                    {list.map((e) => (
                      <Link
                        key={e.id}
                        href={`/events/${e.id}`}
                        onClick={(ev) => ev.stopPropagation()}
                        className={cn("block truncate rounded px-1 py-0.5 text-[11px] font-medium", statusTone(e))}
                        title={`${eventLabel(e)} · ${statusLabel(e)}`}
                      >
                        <span className="hidden sm:inline">{e.venue || eventLabel(e)}</span>
                        <span className="sm:hidden">•</span>
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
            {[
              { status: "confirmed", label: "Confirmed", date: "9999-01-01" },
              { status: "tentative", label: "Hold", date: "9999-01-01" },
              { status: "confirmed", label: "Played", date: "1970-01-01" },
              { status: "cancelled", label: "Cancelled", date: "9999-01-01" },
            ].map((l) => (
              <span key={l.label} className="flex items-center gap-1.5">
                <span className={cn("size-3 rounded-sm", statusTone(l as { status: EventStatus; date: string }))} /> {l.label}
              </span>
            ))}
          </div>
        </section>

        <div className="space-y-8">
          <EventList title="Upcoming" events={upcoming} loading={events.loading} error={events.error} onRetry={events.reload} empty="No gigs booked yet. Add one, or import your existing calendar." />
          <EventList title="History" events={history} loading={events.loading} error={null} empty="Past gigs appear here with their flyers and set lists." />
        </div>
      </div>

      <NewEventDialog date={newDate} onClose={() => setNewDate(null)} />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} onDone={events.reload} />
    </div>
  );
}

const FACEBOOK_SYNCED_KEY = "gfs:facebook-synced-at";
const FACEBOOK_AUTO_SYNC_MS = 6 * 60 * 60 * 1000;

type SyncResult = { found: number; created: number; updated: number; unchanged: number };

/** Offers a Facebook sync when the server is connected, and runs one quietly when the last was over 6 hours ago. */
function useFacebookSync(onChanged: () => void) {
  const status = useFetch<{ configured: boolean }>("/api/events/facebook");
  const [busy, setBusy] = useState(false);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);

  const sync = useCallback(
    async (quiet: boolean) => {
      setBusy(true);
      try {
        const r = await api<SyncResult>("/api/events/facebook", { method: "POST" });
        const now = new Date();
        localStorage.setItem(FACEBOOK_SYNCED_KEY, String(now.getTime()));
        setLastSynced(now);
        if (r.created || r.updated) onChanged();
        if (!quiet || r.created || r.updated) {
          toast.success(
            r.created || r.updated
              ? `Facebook: ${r.created} new gig${r.created === 1 ? "" : "s"}${r.updated ? `, ${r.updated} updated` : ""}.`
              : `Facebook: all ${r.found} upcoming gigs are up to date.`,
          );
        }
      } catch (e) {
        if (!quiet) toast.error(e instanceof Error ? e.message : "Facebook sync failed");
      } finally {
        setBusy(false);
      }
    },
    [onChanged],
  );

  const configured = status.data?.configured === true;
  useEffect(() => {
    if (!configured) return;
    const last = Number(localStorage.getItem(FACEBOOK_SYNCED_KEY) ?? 0);
    if (Date.now() - last <= FACEBOOK_AUTO_SYNC_MS) return;
    const timer = setTimeout(() => void sync(true), 0);
    return () => clearTimeout(timer);
  }, [configured, sync]);

  return { configured, busy, lastSynced, sync };
}

function EventList({ title, events, loading, error, onRetry, empty }: { title: string; events: CalendarEvent[]; loading: boolean; error: string | null; onRetry?: () => void; empty: string }) {
  return (
    <section>
      <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
        {title} {!loading && <span className="text-xs normal-case tracking-normal">{events.length}</span>}
      </h2>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">
          {error}{" "}
          <Button variant="link" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : !events.length ? (
        <p className="rounded-md border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {events.map((e) => (
            <li key={e.id}>
              <Link href={`/events/${e.id}`} className="flex items-center gap-3 rounded-md border border-border/60 bg-card/40 p-2 transition-colors hover:border-foreground/40">
                <DateBlock date={e.date} />
                <div className="min-w-0 flex-1">
                  <div className={cn("truncate font-medium", e.status === "cancelled" && "text-muted-foreground line-through")}>{eventLabel(e)}</div>
                  <div className="truncate text-xs text-muted-foreground">{[e.title ? e.venue : "", e.city, e.showTime && `Show ${e.showTime}`].filter(Boolean).join(" · ") || "Details TBA"}</div>
                  <div className="mt-1 flex items-center gap-3 text-[11px] text-muted-foreground">
                    <span className={cn("rounded px-1.5 py-px", statusTone(e))}>{statusLabel(e)}</span>
                    <span className="flex items-center gap-1">
                      <FileText className="size-3" /> {e.flyerCount ?? 0}
                    </span>
                    <span className="flex items-center gap-1">
                      <ListMusic className="size-3" /> {e.setlistCount ?? 0}
                    </span>
                  </div>
                </div>
                {e.coverFlyer && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={withBase(`/api/flyers/${e.coverFlyer.id}/versions/${e.coverFlyer.versionId}/thumb`)} alt="" className="h-14 w-10 shrink-0 rounded-sm object-cover" loading="lazy" />
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function NewEventDialog({ date, onClose }: { date: string | null; onClose: () => void }) {
  const router = useRouter();
  const [form, setForm] = useState({ date: "", venue: "", city: "", title: "", doors: "", showTime: "", support: "", status: "confirmed" as EventStatus, withSchedule: true });
  const [prevDate, setPrevDate] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  if (date !== prevDate) {
    setPrevDate(date);
    if (date) setForm((f) => ({ ...f, date }));
  }
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  const create = async () => {
    setSaving(true);
    try {
      const ev = await api<CalendarEvent>("/api/events", {
        method: "POST",
        json: { ...form, support: form.support.split(",").map((s) => s.trim()).filter(Boolean) },
      });
      router.push(`/events/${ev.id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not create the gig");
      setSaving(false);
    }
  };

  return (
    <Dialog open={date !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New gig</DialogTitle>
          <DialogDescription>Add the basics now. Logistics, flyers and set lists live on the gig page.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date">
            <Input type="date" value={form.date} onChange={(e) => set("date", e.target.value)} />
          </Field>
          <Field label="Status">
            <Choice
              value={form.status}
              onChange={(v) => set("status", v)}
              options={[
                { value: "confirmed", label: "Confirmed" },
                { value: "tentative", label: "Hold (tentative)" },
              ]}
            />
          </Field>
          <Field label="Venue">
            <Input value={form.venue} onChange={(e) => set("venue", e.target.value)} placeholder="The Camel" autoFocus />
          </Field>
          <Field label="City">
            <Input value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="Richmond, VA" />
          </Field>
          <Field label="Doors">
            <Input value={form.doors} onChange={(e) => set("doors", e.target.value)} placeholder="8pm" />
          </Field>
          <Field label="Show">
            <Input value={form.showTime} onChange={(e) => set("showTime", e.target.value)} placeholder="9pm" />
          </Field>
          <Field label="Support acts" hint="Comma-separated" className="sm:col-span-2">
            <Input value={form.support} onChange={(e) => set("support", e.target.value)} placeholder="Low Tide, The Wrens" />
          </Field>
          <Field label="Event name (optional)" className="sm:col-span-2">
            <Input value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Record release show" />
          </Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Switch checked={form.withSchedule} onCheckedChange={(v) => set("withSchedule", v)} /> Start with a typical run of show (load-in, soundcheck, doors, sets)
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={create} disabled={saving || !form.date}>
            {saving ? "Creating…" : "Create gig"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ImportDialog({ open, onOpenChange, onDone }: { open: boolean; onOpenChange: (o: boolean) => void; onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const ics = await file.text();
      const r = await api<{ found: number; matched: number; created: number; updated: number }>("/api/events/import", { method: "POST", json: { ics, onlyMatching: filter } });
      toast.success(`Imported ${r.created} new gig${r.created === 1 ? "" : "s"}${r.updated ? `, updated ${r.updated}` : ""} (${r.matched} of ${r.found} calendar events matched).`);
      onOpenChange(false);
      setFile(null);
      onDone();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import a calendar</DialogTitle>
          <DialogDescription>
            Bring in past and upcoming gigs from Google Calendar, Apple Calendar or any app that exports .ics. Re-importing the same file updates gigs instead of duplicating them.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <input ref={fileRef} type="file" accept=".ics,text/calendar" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Button variant="outline" className="w-full justify-start" onClick={() => fileRef.current?.click()}>
            <Upload /> {file ? file.name : "Choose .ics file"}
          </Button>
          <Field label="Only events containing (optional)" hint="Useful for a shared calendar, e.g. “gig” or your band name.">
            <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="gig" />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={run} disabled={!file || busy}>
            {busy ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
