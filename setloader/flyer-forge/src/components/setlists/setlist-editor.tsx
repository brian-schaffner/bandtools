"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowDown, ArrowLeft, ArrowUp, CalendarDays, Heading, MoreHorizontal, Plus, Printer, Trash2, Type } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Choice, Field } from "@/components/fields";
import { useFetch } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import {
  eventLabel,
  formatDuration,
  parseDuration,
  parseSetlistText,
  setlistToText,
  songKey,
  songNumbers,
  totalDuration,
  type CalendarEvent,
  type Setlist,
  type SetlistItem,
  type SongStat,
} from "@/lib/events";
import { cn } from "@/lib/utils";

export function SetlistEditor() {
  const { id } = useParams<{ id: string }>();
  const q = useFetch<Setlist>(`/api/setlists/${id}`);
  if (q.error)
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <p className="text-sm text-destructive">{q.error}</p>
        <Link href="/setlists" className={buttonVariants({ variant: "link" })}>
          Back to set lists
        </Link>
      </div>
    );
  if (!q.data)
    return (
      <div className="mx-auto w-full max-w-4xl space-y-4 px-4 py-8 sm:px-6">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-96" />
      </div>
    );
  return <Editor key={q.data.updatedAt} setlist={q.data} onSaved={(s) => q.setData(s)} />;
}

type Row = SetlistItem & { rid: string };
let seq = 0;
const withKey = (i: SetlistItem): Row => ({ ...i, rid: `i${++seq}` });

function Editor({ setlist, onSaved }: { setlist: Setlist; onSaved: (s: Setlist) => void }) {
  const router = useRouter();
  const events = useFetch<CalendarEvent[]>("/api/events");
  const stats = useFetch<Record<string, SongStat>>(`/api/songs?exclude=${setlist.id}`);
  const [name, setName] = useState(setlist.name);
  const [eventId, setEventId] = useState<string | null>(setlist.eventId);
  const [notes, setNotes] = useState(setlist.notes);
  const [rows, setRows] = useState<Row[]>(() => setlist.items.map(withKey));
  const [textMode, setTextMode] = useState(false);
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  const items: SetlistItem[] = rows.map(({ rid, ...i }) => (void rid, i));
  const numbers = songNumbers(items);
  const dirty = name !== setlist.name || eventId !== setlist.eventId || notes !== setlist.notes || JSON.stringify(items) !== JSON.stringify(setlist.items);
  const totals = totalDuration(items);
  const update = (rid: string, p: Partial<SetlistItem>) => setRows((rs) => rs.map((r) => (r.rid === rid ? { ...r, ...p } : r)));
  const move = (i: number, d: number) =>
    setRows((rs) => {
      const j = i + d;
      if (j < 0 || j >= rs.length) return rs;
      const next = [...rs];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });

  const save = async () => {
    setSaving(true);
    try {
      const s = await api<Setlist>(`/api/setlists/${setlist.id}`, { method: "PATCH", json: { name, eventId, notes, items: items.filter((i) => i.title.trim()) } });
      toast.success("Set list saved");
      onSaved(s);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
      setSaving(false);
    }
  };

  const remove = async () => {
    await api(`/api/setlists/${setlist.id}`, { method: "DELETE" });
    toast.success("Set list deleted");
    router.push(setlist.eventId ? `/events/${setlist.eventId}` : "/setlists");
  };

  const linked = events.data?.find((e) => e.id === eventId) ?? null;
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href={setlist.eventId ? `/events/${setlist.eventId}` : "/setlists"} className={buttonVariants({ variant: "ghost", size: "icon-sm" })} aria-label="Back">
          <ArrowLeft />
        </Link>
        <Input value={name} onChange={(e) => setName(e.target.value)} className="h-9 max-w-md border-transparent bg-transparent text-lg font-semibold hover:border-input" aria-label="Set list name" />
        <div className="ml-auto flex items-center gap-2">
          <Link href={`/setlists/${setlist.id}/print`} target="_blank" className={buttonVariants({ variant: "outline", size: "sm" })}>
            <Printer /> Stage copy
          </Link>
          <Button size="sm" onClick={save} disabled={!dirty || saving}>
            {saving ? "Saving…" : dirty ? "Save" : "Saved"}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="More" />}>
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem variant="destructive" onClick={remove}>
                Delete set list
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="rounded-lg border border-border/60 bg-card/40 p-3 sm:p-4">
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
            <span className="text-muted-foreground">
              {totals.songs} songs{totals.seconds ? ` · ${formatDuration(totals.seconds)}${totals.unknown ? ` + ${totals.unknown} untimed` : ""}` : ""}
            </span>
            <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
              <Switch
                checked={textMode}
                onCheckedChange={(v) => {
                  if (v) setText(setlistToText(items));
                  else {
                    const parsed = parseSetlistText(text);
                    setRows(parsed.map(withKey));
                  }
                  setTextMode(v);
                }}
              />
              <Type className="size-3.5" /> Edit as text
            </label>
          </div>

          {textMode ? (
            <Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-[420px] font-mono text-sm" />
          ) : (
            <ol className="space-y-1">
              {rows.map((r, i) => {
                if (r.type === "section")
                  return (
                    <li key={r.rid} className="group flex items-center gap-2 pt-3 first:pt-0">
                      <Input value={r.title} onChange={(e) => update(r.rid, { title: e.target.value })} className="h-8 border-transparent bg-transparent text-xs font-semibold uppercase tracking-wider hover:border-input" />
                      <RowActions onUp={() => move(i, -1)} onDown={() => move(i, 1)} onRemove={() => setRows((rs) => rs.filter((x) => x.rid !== r.rid))} />
                    </li>
                  );
                const stat = stats.data?.[songKey(r.title)];
                return (
                  <li key={r.rid} className="group grid grid-cols-[24px_minmax(0,1fr)_56px_64px_auto] items-center gap-2 rounded-md px-1 hover:bg-muted/30 max-sm:grid-cols-[24px_minmax(0,1fr)_auto]">
                    <span className="text-right font-mono text-xs text-muted-foreground tabular-nums">{numbers[i]}</span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Input value={r.title} onChange={(e) => update(r.rid, { title: e.target.value })} className="h-8 border-transparent bg-transparent hover:border-input" aria-label="Song title" />
                        <button
                          onClick={() => update(r.rid, { segue: !r.segue })}
                          className={cn("shrink-0 rounded px-1.5 text-xs", r.segue ? "bg-primary/20 text-primary" : "text-muted-foreground/40 hover:text-muted-foreground")}
                          title="Segue into the next song"
                        >
                          →
                        </button>
                      </div>
                      <div className="flex items-center gap-2 pl-3 text-[11px] text-muted-foreground">
                        {stats.data && r.title.trim() && <span className={cn(!stat && "text-emerald-400")}>{stat ? `played ${stat.count}× before · last ${stat.lastDate}` : "first time"}</span>}
                        <input value={r.notes} onChange={(e) => update(r.rid, { notes: e.target.value })} placeholder="notes" className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground/40" />
                      </div>
                    </div>
                    <Input value={r.key} onChange={(e) => update(r.rid, { key: e.target.value })} placeholder="key" className="h-8 font-mono text-xs max-sm:hidden" aria-label="Key" />
                    <DurationInput value={r.duration} onChange={(d) => update(r.rid, { duration: d })} />
                    <RowActions onUp={() => move(i, -1)} onDown={() => move(i, 1)} onRemove={() => setRows((rs) => rs.filter((x) => x.rid !== r.rid))} />
                  </li>
                );
              })}
            </ol>
          )}
          {!textMode && (
            <div className="mt-3 flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setRows((rs) => [...rs, withKey({ type: "song", title: "", duration: null, key: "", notes: "", segue: false })])}>
                <Plus /> Song
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setRows((rs) => [...rs, withKey({ type: "section", title: "Encore", duration: null, key: "", notes: "", segue: false })])}>
                <Heading /> Section
              </Button>
            </div>
          )}
        </section>

        <aside className="space-y-5">
          <Field label="Gig" hint={linked ? undefined : "File it under a date so it shows in the calendar history."}>
            <Choice
              value={eventId ?? "none"}
              onChange={(v) => setEventId(v === "none" ? null : v)}
              options={[{ value: "none", label: "Not filed under a gig" }, ...[...(events.data ?? [])].reverse().map((e) => ({ value: e.id, label: `${e.date} · ${eventLabel(e)}` }))]}
            />
          </Field>
          {linked && (
            <Link href={`/events/${linked.id}`} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
              <CalendarDays className="size-4" /> Open gig: {eventLabel(linked)}
            </Link>
          )}
          <Field label="Notes" hint="Tunings, gear changes, who's counting in…">
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="min-h-32" />
          </Field>
        </aside>
      </div>
    </div>
  );
}

function RowActions({ onUp, onDown, onRemove }: { onUp: () => void; onDown: () => void; onRemove: () => void }) {
  return (
    <div className="flex shrink-0 items-center opacity-60 transition-opacity group-hover:opacity-100">
      <Button variant="ghost" size="icon-xs" onClick={onUp} aria-label="Move up">
        <ArrowUp />
      </Button>
      <Button variant="ghost" size="icon-xs" onClick={onDown} aria-label="Move down">
        <ArrowDown />
      </Button>
      <Button variant="ghost" size="icon-xs" onClick={onRemove} aria-label="Remove">
        <Trash2 />
      </Button>
    </div>
  );
}

function DurationInput({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  const [text, setText] = useState(formatDuration(value));
  return (
    <Input
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        const d = text.trim() ? parseDuration(text) : null;
        if (text.trim() && d == null) setText(formatDuration(value));
        else onChange(d);
      }}
      placeholder="m:ss"
      className="h-8 font-mono text-xs tabular-nums max-sm:hidden"
      aria-label="Duration"
    />
  );
}
