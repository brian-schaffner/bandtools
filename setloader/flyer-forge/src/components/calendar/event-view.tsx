"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { AlertTriangle, ArrowLeft, ArrowRight, Clock, FileText, ListMusic, MoreHorizontal, Plus, Trash2, Wand2 } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Choice, Field } from "@/components/fields";
import { SetlistLoader } from "@/components/setlists/setlist-loader";
import { DateBlock, statusTone } from "./calendar-view";
import { useFetch } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import { withBase } from "@/lib/session";
import {
  briefMismatches,
  eventLabel,
  formatDuration,
  SCHEDULE_KINDS,
  SCHEDULE_LABELS,
  statusLabel,
  totalDuration,
  type CalendarEvent,
  type EventFields,
  type ScheduleItem,
  type Setlist,
} from "@/lib/events";
import { FORMATS, type FormatId } from "@/lib/spec";
import type { Flyer } from "@/lib/types";
import { cn } from "@/lib/utils";

type EventDetail = { event: CalendarEvent; schedule: ScheduleItem[]; flyers: Flyer[]; setlists: Setlist[] };

export function EventView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const q = useFetch<EventDetail>(`/api/events/${id}`);
  const [loaderOpen, setLoaderOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (q.error)
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <p className="text-sm text-destructive">{q.error}</p>
        <Link href="/calendar" className={buttonVariants({ variant: "link" })}>
          Back to calendar
        </Link>
      </div>
    );
  if (!q.data)
    return (
      <div className="mx-auto grid w-full max-w-[1500px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Skeleton className="h-[520px]" />
        <div className="space-y-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );

  const { event, schedule, flyers, setlists } = q.data;
  const patch = (p: Partial<EventDetail>) => q.setData((d) => (d ? { ...d, ...p } : d));

  const remove = async () => {
    try {
      await api(`/api/events/${event.id}`, { method: "DELETE" });
      toast.success("Gig removed. Its flyers and set lists were kept.");
      router.push("/calendar");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not delete");
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link href="/calendar" className={buttonVariants({ variant: "ghost", size: "icon-sm" })} aria-label="Back to calendar">
          <ArrowLeft />
        </Link>
        <DateBlock date={event.date} />
        <div className="min-w-0 flex-1">
          <h1 className={cn("truncate text-2xl font-semibold tracking-tight", event.status === "cancelled" && "text-muted-foreground line-through")}>{eventLabel(event)}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className={cn("rounded px-1.5 py-px text-xs", statusTone(event))}>{statusLabel(event)}</span>
            {[event.title ? event.venue : "", event.city].filter(Boolean).join(" · ")}
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="More" />}>
            <MoreHorizontal />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem variant="destructive" onClick={() => setConfirmDelete(true)}>
              Delete gig
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <DetailsCard key={event.updatedAt} event={event} onSaved={(e) => patch({ event: e })} />
        <div className="space-y-6">
          <ScheduleCard key={schedule.map((s) => s.id).join()} eventId={event.id} schedule={schedule} onSaved={(s) => patch({ schedule: s })} />
          <FlyersCard event={event} flyers={flyers} />
          <SetlistsCard setlists={setlists} onLoad={() => setLoaderOpen(true)} />
        </div>
      </div>

      <SetlistLoader
        open={loaderOpen}
        onOpenChange={setLoaderOpen}
        eventId={event.id}
        defaultName={`${event.venue || "Gig"} · ${event.date}`}
        onCreated={(s) => patch({ setlists: [...setlists, s] })}
      />
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this gig?</AlertDialogTitle>
            <AlertDialogDescription>The logistics schedule is deleted. Flyers and set lists are kept but no longer filed under a date. To keep the history, mark it cancelled instead.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={remove}>
              Delete gig
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Card({ title, icon, action, children, className }: { title: string; icon: React.ReactNode; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-lg border border-border/60 bg-card/40 p-4 sm:p-5", className)}>
      <div className="mb-4 flex items-center gap-2">
        <span className="text-muted-foreground">{icon}</span>
        <h2 className="font-medium">{title}</h2>
        <div className="ml-auto flex items-center gap-2">{action}</div>
      </div>
      {children}
    </section>
  );
}

function DetailsCard({ event, onSaved }: { event: CalendarEvent; onSaved: (e: CalendarEvent) => void }) {
  const [draft, setDraft] = useState<EventFields>(() => pick(event));
  const [supportText, setSupportText] = useState(event.support.join(", "));
  const [saving, setSaving] = useState(false);
  const set = <K extends keyof EventFields>(k: K, v: EventFields[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const support = supportText.split(",").map((s) => s.trim()).filter(Boolean);
  const dirty = JSON.stringify({ ...draft, support }) !== JSON.stringify({ ...pick(event), support: event.support });

  const save = async () => {
    setSaving(true);
    try {
      onSaved(await api<CalendarEvent>(`/api/events/${event.id}`, { method: "PATCH", json: { ...draft, support } }));
      toast.success("Gig details saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
      setSaving(false);
    }
  };

  return (
    <Card
      title="Gig & venue"
      icon={<FileText className="size-4" />}
      action={
        <Button size="sm" onClick={save} disabled={!dirty || saving || !draft.date}>
          {saving ? "Saving…" : dirty ? "Save details" : "Saved"}
        </Button>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Date">
          <Input type="date" value={draft.date} onChange={(e) => set("date", e.target.value)} />
        </Field>
        <Field label="Status">
          <Choice
            value={draft.status}
            onChange={(v) => set("status", v)}
            options={[
              { value: "confirmed", label: "Confirmed" },
              { value: "tentative", label: "Hold (tentative)" },
              { value: "cancelled", label: "Cancelled" },
            ]}
          />
        </Field>
        <Field label="Event name" hint="Optional, e.g. “Record release”" className="sm:col-span-2">
          <Input value={draft.title} onChange={(e) => set("title", e.target.value)} />
        </Field>
        <Field label="Venue">
          <Input value={draft.venue} onChange={(e) => set("venue", e.target.value)} placeholder="The Camel" />
        </Field>
        <Field label="City">
          <Input value={draft.city} onChange={(e) => set("city", e.target.value)} placeholder="Richmond, VA" />
        </Field>
        <Field label="Address" className="sm:col-span-2">
          <Input value={draft.address} onChange={(e) => set("address", e.target.value)} placeholder="1621 W Broad St, Richmond, VA" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Doors">
            <Input value={draft.doors} onChange={(e) => set("doors", e.target.value)} placeholder="8pm" />
          </Field>
          <Field label="Show">
            <Input value={draft.showTime} onChange={(e) => set("showTime", e.target.value)} placeholder="9pm" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Price">
            <Input value={draft.price} onChange={(e) => set("price", e.target.value)} placeholder="$12 adv" />
          </Field>
          <Field label="Ages">
            <Input value={draft.ages} onChange={(e) => set("ages", e.target.value)} placeholder="21+" />
          </Field>
        </div>
        <Field label="Support acts" hint="Comma-separated">
          <Input value={supportText} onChange={(e) => setSupportText(e.target.value)} placeholder="Low Tide, The Wrens" />
        </Field>
        <Field label="Tickets / link">
          <Input value={draft.tickets} onChange={(e) => set("tickets", e.target.value)} />
        </Field>
      </div>
      <h3 className="mb-3 mt-6 text-xs font-medium uppercase tracking-wide text-muted-foreground">Logistics</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Venue contact">
          <Input value={draft.contactName} onChange={(e) => set("contactName", e.target.value)} placeholder="Name" />
        </Field>
        <Field label="Phone">
          <Input value={draft.contactPhone} onChange={(e) => set("contactPhone", e.target.value)} type="tel" />
        </Field>
        <Field label="Email">
          <Input value={draft.contactEmail} onChange={(e) => set("contactEmail", e.target.value)} type="email" />
        </Field>
        <Field label="Deal / pay" className="sm:col-span-3">
          <Input value={draft.deal} onChange={(e) => set("deal", e.target.value)} placeholder="$300 guarantee vs 70% door, 2 drink tickets each" />
        </Field>
        <Field label="Notes" hint="Parking, load-in door, backline, hospitality, merch…" className="sm:col-span-3">
          <Textarea value={draft.notes} onChange={(e) => set("notes", e.target.value)} className="min-h-28" />
        </Field>
      </div>
    </Card>
  );
}

function pick(e: CalendarEvent): EventFields {
  const { title, date, status, venue, city, address, doors, showTime, price, ages, support, tickets, contactName, contactPhone, contactEmail, deal, notes } = e;
  return { title, date, status, venue, city, address, doors, showTime, price, ages, support, tickets, contactName, contactPhone, contactEmail, deal, notes };
}

type Row = Omit<ScheduleItem, "id"> & { key: string };
let rowSeq = 0;
const rowKey = () => `r${++rowSeq}`;

function ScheduleCard({ eventId, schedule, onSaved }: { eventId: string; schedule: ScheduleItem[]; onSaved: (s: ScheduleItem[]) => void }) {
  const initial = schedule.map((s) => ({ ...s, key: s.id }));
  const [rows, setRows] = useState<Row[]>(initial);
  const [saving, setSaving] = useState(false);
  const strip = (r: Row[]) => JSON.stringify(r.map(({ time, label, kind, notes }) => ({ time, label, kind, notes })));
  const dirty = strip(rows) !== strip(initial);
  const valid = rows.every((r) => r.label.trim());

  const put = async (body: object) => {
    setSaving(true);
    try {
      onSaved(await api<ScheduleItem[]>(`/api/events/${eventId}/schedule`, { method: "PUT", json: body }));
      toast.success("Schedule saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save schedule");
      setSaving(false);
    }
  };
  const update = (key: string, p: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  return (
    <Card
      title="Run of show"
      icon={<Clock className="size-4" />}
      action={
        rows.length > 0 && (
          <Button size="sm" onClick={() => put({ items: rows.map(({ time, label, kind, notes }) => ({ time, label, kind, notes })) })} disabled={!dirty || saving || !valid}>
            {saving ? "Saving…" : dirty ? "Save schedule" : "Saved"}
          </Button>
        )
      }
    >
      {rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-border p-5 text-center">
          <p className="text-sm text-muted-foreground">No schedule yet.</p>
          <div className="mt-3 flex justify-center gap-2">
            <Button size="sm" variant="outline" onClick={() => put({ template: "default" })} disabled={saving}>
              <Wand2 /> Typical club night
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRows([{ key: rowKey(), time: "", label: "", kind: "other", notes: "" }])}>
              <Plus /> Add a slot
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.key} className="grid grid-cols-[72px_120px_minmax(0,1fr)_32px] items-center gap-2 max-sm:grid-cols-[64px_minmax(0,1fr)_32px]">
              <Input value={r.time} onChange={(e) => update(r.key, { time: e.target.value })} placeholder="18:30" className="font-mono text-xs tabular-nums" aria-label="Time" />
              <div className="max-sm:hidden">
                <Choice
                  value={r.kind}
                  onChange={(v) => update(r.key, { kind: v, label: r.label || SCHEDULE_LABELS[v] })}
                  options={SCHEDULE_KINDS.map((k) => ({ value: k, label: SCHEDULE_LABELS[k] }))}
                />
              </div>
              <Input value={r.label} onChange={(e) => update(r.key, { label: e.target.value })} placeholder="What happens" aria-label="Label" />
              <Button variant="ghost" size="icon-sm" onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))} aria-label="Remove slot">
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button size="sm" variant="ghost" onClick={() => setRows((rs) => [...rs, { key: rowKey(), time: "", label: "", kind: "other", notes: "" }])}>
            <Plus /> Add a slot
          </Button>
          <p className="text-xs text-muted-foreground">Slots are sorted by time when saved. Times after midnight stay at the end of the night.</p>
        </div>
      )}
    </Card>
  );
}

function FlyersCard({ event, flyers }: { event: CalendarEvent; flyers: Flyer[] }) {
  return (
    <Card
      title="Flyers"
      icon={<FileText className="size-4" />}
      action={
        <Link href={`/flyers/new?event=${event.id}`} className={buttonVariants({ size: "sm", variant: flyers.length ? "outline" : "default" })}>
          <Plus /> Design a flyer
        </Link>
      }
    >
      {!flyers.length ? (
        <p className="text-sm text-muted-foreground">No flyer for this gig yet. Gig details carry straight into the flyer brief.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {flyers.map((f) => {
            const fmt = FORMATS[(f.format as FormatId) ?? f.brief.format] ?? FORMATS["poster-11x17"];
            const diff = briefMismatches(event, f.brief);
            return (
              <Link key={f.id} href={`/flyers/${f.id}`} className="group block">
                <div className="overflow-hidden rounded-md border border-border/60 bg-muted transition-colors group-hover:border-foreground/40" style={{ aspectRatio: `${fmt.w} / ${fmt.h}` }}>
                  {f.currentVersionId && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={withBase(`/api/flyers/${f.id}/versions/${f.currentVersionId}/thumb`)} alt={f.title} className="h-full w-full object-cover" loading="lazy" />
                  )}
                </div>
                <div className="mt-1.5 truncate text-xs text-muted-foreground">{fmt.label.split(" · ")[0]}</div>
                {diff.length > 0 && (
                  <div className="mt-1 flex items-start gap-1 text-[11px] text-amber-300" title={diff.map((d) => `${d.label}: flyer “${d.flyer}”, calendar “${d.event}”`).join("\n")}>
                    <AlertTriangle className="mt-px size-3 shrink-0" />
                    <span>Out of date: {diff.map((d) => d.label.toLowerCase()).join(", ")}</span>
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function SetlistsCard({ setlists, onLoad }: { setlists: Setlist[]; onLoad: () => void }) {
  return (
    <Card
      title="Set lists"
      icon={<ListMusic className="size-4" />}
      action={
        <Button size="sm" variant={setlists.length ? "outline" : "default"} onClick={onLoad}>
          <Plus /> Load set list
        </Button>
      }
    >
      {!setlists.length ? (
        <p className="text-sm text-muted-foreground">Paste, upload or copy a previous set list. It&apos;s kept with this date so you can see what you played where.</p>
      ) : (
        <ul className="space-y-2">
          {setlists.map((s) => {
            const t = totalDuration(s.items);
            const first = s.items.filter((i) => i.type === "song").slice(0, 4).map((i) => i.title);
            return (
              <li key={s.id}>
                <Link href={`/setlists/${s.id}`} className="flex items-center gap-3 rounded-md border border-border/60 p-3 transition-colors hover:border-foreground/40">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{s.name}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {t.songs} songs{t.seconds ? ` · ${formatDuration(t.seconds)}` : ""} · {first.join(", ")}
                      {t.songs > first.length ? "…" : ""}
                    </div>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
