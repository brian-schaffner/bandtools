"use client";

import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Choice, Field } from "@/components/fields";
import { useFetch } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import { eventLabel, formatDuration, parseSetlistText, songNumbers, totalDuration, type Setlist, type SetlistItem } from "@/lib/events";
import { cn } from "@/lib/utils";

const EXAMPLE = `SET 1
1. Static Bloom [E] 3:45
2. Low Ceiling 4:10 ->
3. Glasshouse (capo 2) 3:20
ENCORE
4. Velvet Hour [Am] 5:02`;

export function SetlistLoader({
  open,
  onOpenChange,
  eventId,
  defaultName,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  eventId: string | null;
  defaultName: string;
  onCreated: (s: Setlist) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"paste" | "file" | "copy">("paste");
  const [name, setName] = useState(defaultName);
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [copyId, setCopyId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setName(defaultName);
      setText("");
      setFileName(null);
      setCopyId(null);
    }
  }
  const previous = useFetch<Setlist[]>(open && tab === "copy" ? "/api/setlists" : null);

  const items: SetlistItem[] = useMemo(() => {
    if (tab === "copy") return previous.data?.find((s) => s.id === copyId)?.items ?? [];
    return parseSetlistText(text);
  }, [tab, text, copyId, previous.data]);
  const totals = totalDuration(items);

  const readFile = async (f: File) => {
    if (f.size > 500_000) return toast.error("That file is too big for a set list (500 KB max).");
    setFileName(f.name);
    setText(await f.text());
    if (name === defaultName) setName(f.name.replace(/\.[^.]+$/, ""));
  };

  const save = async () => {
    setSaving(true);
    try {
      const s = await api<Setlist>("/api/setlists", { method: "POST", json: { name: name.trim() || defaultName, eventId, items, source: tab === "paste" ? "paste" : tab } });
      toast.success(`Loaded ${totalDuration(s.items).songs} songs`);
      onCreated(s);
      onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save the set list");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Load a set list</DialogTitle>
          <DialogDescription>Paste it the way you&apos;d write it, upload a .txt or .csv, or start from a previous gig. Numbers, keys like [E], times like 3:45, “Set 2”/“Encore” headers and -&gt; segues are picked up automatically.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-4">
            <Field label="Name">
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
              <TabsList className="w-full">
                <TabsTrigger value="paste">Paste</TabsTrigger>
                <TabsTrigger value="file">Upload file</TabsTrigger>
                <TabsTrigger value="copy">Copy previous</TabsTrigger>
              </TabsList>
              <TabsContent value="paste" className="pt-3">
                <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={EXAMPLE} className="min-h-64 font-mono text-xs" />
              </TabsContent>
              <TabsContent value="file" className="space-y-2 pt-3">
                <input ref={fileRef} type="file" accept=".txt,.csv,.md,text/plain,text/csv" className="hidden" onChange={(e) => e.target.files?.[0] && void readFile(e.target.files[0])} />
                <button
                  onClick={() => fileRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files[0];
                    if (f) void readFile(f);
                  }}
                  className="grid h-40 w-full place-items-center rounded-md border border-dashed border-border text-sm text-muted-foreground transition-colors hover:border-foreground/40"
                >
                  <span className="flex flex-col items-center gap-2">
                    <Upload className="size-5" />
                    {fileName ?? "Drop a .txt or .csv here, or click to choose"}
                  </span>
                </button>
                <p className="text-xs text-muted-foreground">CSV needs a header row with a title (or song) column; duration, key and notes columns are optional.</p>
              </TabsContent>
              <TabsContent value="copy" className="pt-3">
                {previous.loading ? (
                  <p className="text-sm text-muted-foreground">Loading set lists…</p>
                ) : !previous.data?.length ? (
                  <p className="text-sm text-muted-foreground">No set lists yet. Paste or upload your first one.</p>
                ) : (
                  <Choice
                    value={copyId}
                    onChange={setCopyId}
                    placeholder="Choose a set list"
                    options={previous.data.map((s) => ({ value: s.id, label: `${s.event ? `${s.event.date} · ${eventLabel(s.event)} — ` : ""}${s.name}` }))}
                  />
                )}
              </TabsContent>
            </Tabs>
          </div>
          <div className="min-w-0">
            <div className="mb-2 flex items-baseline justify-between text-xs text-muted-foreground">
              <span className="font-medium uppercase tracking-wide">Preview</span>
              <span>
                {totals.songs} songs{totals.seconds ? ` · ${formatDuration(totals.seconds)}${totals.unknown ? "+" : ""}` : ""}
              </span>
            </div>
            <SetlistPreview items={items} className="max-h-80" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving || !items.some((i) => i.type === "song")}>
            {saving ? "Saving…" : "Save set list"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function SetlistPreview({ items, className }: { items: SetlistItem[]; className?: string }) {
  const numbers = songNumbers(items);
  if (!items.length) return <div className={cn("grid h-40 place-items-center rounded-md border border-dashed border-border text-sm text-muted-foreground", className)}>Songs will appear here</div>;
  return (
    <ol className={cn("overflow-y-auto rounded-md border border-border/60 bg-card/40 p-2 text-sm", className)}>
      {items.map((it, i) =>
        it.type === "section" ? (
          <li key={i} className="mt-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground first:mt-0">
            {it.title}
          </li>
        ) : (
          <li key={i} className="flex items-baseline gap-2 rounded px-1 py-0.5">
            <span className="w-5 text-right font-mono text-xs text-muted-foreground tabular-nums">{numbers[i]}</span>
            <span className="min-w-0 flex-1 truncate">
              {it.title}
              {it.segue && <span className="ml-1 text-muted-foreground">→</span>}
              {it.notes && <span className="ml-2 text-xs text-muted-foreground">{it.notes}</span>}
            </span>
            {it.key && <span className="rounded bg-muted px-1 font-mono text-[11px]">{it.key}</span>}
            <span className="w-10 text-right font-mono text-xs text-muted-foreground tabular-nums">{formatDuration(it.duration)}</span>
          </li>
        ),
      )}
    </ol>
  );
}
