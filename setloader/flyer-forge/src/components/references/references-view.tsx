"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Ban, MoreHorizontal, Plus, Sparkles, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Choice, Field } from "@/components/fields";
import { FlyerCanvas } from "@/components/flyer-canvas";
import { useAiStatus, useRefs } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import { blobToImage, uploadAsset } from "@/lib/assets-client";
import { withBase } from "@/lib/session";
import { buildSpec, RECIPE_MAP, RECIPES } from "@/lib/recipes";
import { BriefSchema } from "@/lib/spec";
import type { Asset, StyleRef } from "@/lib/types";
import { cn } from "@/lib/utils";

const SAMPLE_BRIEF = BriefSchema.parse({
  date: "2026-12-12",
  venue: "The Broadberry",
  city: "Richmond",
  showTime: "9pm",
  doors: "8pm",
  price: "$15",
  support: ["Low Tide"],
});

const EMPTY_IMAGES = new Map();

function RecipeSwatch({ recipeId }: { recipeId: string }) {
  const spec = useMemo(
    () => buildSpec(recipeId, { brief: SAMPLE_BRIEF, bandName: "Band Name", format: "ig-portrait", photo: { id: "sample", width: 3, height: 2 }, logo: null, seed: 7 }),
    [recipeId],
  );
  return <FlyerCanvas spec={spec} images={EMPTY_IMAGES} wireframe resolution={320} className="rounded-none" />;
}

export function ReferencesView() {
  const refs = useRefs();
  const ai = useAiStatus();
  const [tab, setTab] = useState<"avoid" | "inspire">("avoid");
  const [editing, setEditing] = useState<Partial<StyleRef> | null>(null);
  const list = refs.data ?? [];
  const byKind = (k: "avoid" | "inspire") => list.filter((r) => r.kind === k);

  const archive = async (r: StyleRef) => {
    try {
      await api(`/api/references/${r.id}`, { method: "PATCH", json: { archived: true } });
      refs.setData((l) => l?.filter((x) => x.id !== r.id));
      toast.success("Removed from the rulebook", { description: "Seeded references can be re-added any time from your notes." });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not update");
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">References</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            The rulebook behind every concept and critique. <strong className="text-foreground">Avoid</strong> collects what makes a flyer read as
            AI-generated; <strong className="text-foreground">Inspire</strong> collects traditional print work worth stealing from. Add your own
            examples. With Claude connected, uploads are analysed into rules automatically.
          </p>
        </div>
        <Button onClick={() => setEditing({ kind: tab, traits: [] })}>
          <Plus /> Add reference
        </Button>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as "avoid" | "inspire")}>
        <TabsList>
          <TabsTrigger value="avoid">What not to do · {byKind("avoid").length}</TabsTrigger>
          <TabsTrigger value="inspire">Inspiration · {byKind("inspire").length}</TabsTrigger>
        </TabsList>
        {(["avoid", "inspire"] as const).map((k) => (
          <TabsContent key={k} value={k} className="mt-4">
            {refs.loading ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 6 }, (_, i) => (
                  <Skeleton key={i} className="h-56" />
                ))}
              </div>
            ) : refs.error ? (
              <p className="text-sm text-destructive">{refs.error}</p>
            ) : byKind(k).length === 0 ? (
              <p className="rounded-md bg-muted/30 px-4 py-10 text-center text-sm text-muted-foreground">Nothing here yet. Add a reference to shape the rulebook.</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {byKind(k).map((r) => (
                  <RefCard key={r.id} r={r} onEdit={() => setEditing(r)} onArchive={() => archive(r)} />
                ))}
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>

      <RefDialog
        value={editing}
        aiEnabled={!!ai?.enabled}
        onClose={() => setEditing(null)}
        onSaved={(r) => {
          refs.setData((l) => (l ? (l.some((x) => x.id === r.id) ? l.map((x) => (x.id === r.id ? r : x)) : [...l, r]) : [r]));
          setTab(r.kind);
          setEditing(null);
        }}
      />
    </div>
  );
}

function RefCard({ r, onEdit, onArchive }: { r: StyleRef; onEdit: () => void; onArchive: () => void }) {
  const recipe = r.recipeId ? RECIPE_MAP[r.recipeId] : null;
  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border/60 bg-card">
      <div className="flex gap-3 p-4">
        <div className="w-24 shrink-0">
          {r.imageAssetId ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={withBase(`/api/assets/${r.imageAssetId}/preview`)} alt="" className="aspect-[4/5] w-full rounded-sm object-cover" />
          ) : recipe ? (
            <div className="overflow-hidden rounded-sm">
              <RecipeSwatch recipeId={recipe.id} />
            </div>
          ) : (
            <div className={cn("grid aspect-[4/5] w-full place-items-center rounded-sm", r.kind === "avoid" ? "bg-red-500/10 text-red-400" : "bg-muted text-muted-foreground")}>
              {r.kind === "avoid" ? <Ban className="size-7" /> : <Sparkles className="size-7" />}
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-medium leading-snug">{r.title}</h3>
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button size="icon-xs" variant="ghost" aria-label="More" />}>
                <MoreHorizontal />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={onEdit}>Edit</DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onClick={onArchive}>
                  Remove from rulebook
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="flex flex-wrap gap-1">
            {recipe && <Badge variant="secondary">Recipe: {recipe.name}</Badge>}
            {r.seeded && <Badge variant="outline">Starter</Badge>}
          </div>
          <p className="line-clamp-3 text-xs text-muted-foreground">{r.notes}</p>
        </div>
      </div>
      <ul className="mt-auto space-y-1 border-t border-border/60 px-4 py-3 text-xs">
        {r.traits.map((t) => (
          <li key={t} className="flex gap-2">
            <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", r.kind === "avoid" ? "bg-red-400" : "bg-emerald-400")} />
            <span>{t}</span>
          </li>
        ))}
      </ul>
      <button onClick={onEdit} className="border-t border-border/60 px-4 py-2 text-left text-xs text-muted-foreground hover:text-foreground">
        Edit rules
      </button>
    </div>
  );
}

async function previewDataUrl(assetId: string) {
  const blob = await fetch(withBase(`/api/assets/${assetId}/preview`)).then((r) => r.blob());
  const img = await blobToImage(blob);
  const s = Math.min(1, 1024 / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement("canvas");
  c.width = Math.round(img.naturalWidth * s);
  c.height = Math.round(img.naturalHeight * s);
  const cx = c.getContext("2d")!;
  cx.fillStyle = "#fff";
  cx.fillRect(0, 0, c.width, c.height);
  cx.drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.85);
}

function RefDialog({ value, aiEnabled, onClose, onSaved }: { value: Partial<StyleRef> | null; aiEnabled: boolean; onClose: () => void; onSaved: (r: StyleRef) => void }) {
  const [draft, setDraft] = useState<Partial<StyleRef>>({});
  const [traitsText, setTraitsText] = useState("");
  const [busy, setBusy] = useState<"upload" | "analyze" | "save" | null>(null);
  const [prevValue, setPrevValue] = useState<Partial<StyleRef> | null>(null);
  if (value !== prevValue) {
    setPrevValue(value);
    setDraft(value ?? {});
    setTraitsText((value?.traits ?? []).join("\n"));
  }

  const upload = async (file: File) => {
    setBusy("upload");
    try {
      const a: Asset = await uploadAsset(file, { kind: "reference", name: file.name });
      setDraft((d) => ({ ...d, imageAssetId: a.id }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  };

  const analyze = async () => {
    if (!draft.imageAssetId) return;
    setBusy("analyze");
    try {
      const image = await previewDataUrl(draft.imageAssetId);
      const out = await api<{ title: string; notes: string; traits: string[]; recipeId: string | null }>("/api/ai/analyze-reference", {
        method: "POST",
        json: { image, kind: draft.kind ?? "inspire" },
      });
      setDraft((d) => ({ ...d, title: d.title || out.title, notes: out.notes, recipeId: out.recipeId ?? d.recipeId ?? null }));
      setTraitsText(out.traits.join("\n"));
      toast.success("Analysed. Review the rules before saving.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    setBusy("save");
    const body = {
      kind: draft.kind ?? "inspire",
      title: (draft.title ?? "").trim(),
      notes: draft.notes ?? "",
      traits: traitsText
        .split("\n")
        .map((t) => t.replace(/^[-•*]\s*/, "").trim())
        .filter(Boolean),
      recipeId: draft.recipeId ?? null,
      imageAssetId: draft.imageAssetId ?? null,
    };
    try {
      const saved = draft.id
        ? await api<StyleRef>(`/api/references/${draft.id}`, { method: "PATCH", json: body })
        : await api<StyleRef>("/api/references", { method: "POST", json: body });
      onSaved(saved);
      toast.success("Rulebook updated");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={!!value} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{draft.id ? "Edit reference" : "Add reference"}</DialogTitle>
          <DialogDescription>Rules are written as instructions; they&apos;re fed to every concept and critique.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-5 sm:grid-cols-[180px_1fr]">
          <div className="space-y-2">
            <label className="relative grid aspect-[4/5] cursor-pointer place-items-center overflow-hidden rounded-md border border-dashed border-border text-center text-xs text-muted-foreground hover:border-foreground/40">
              {draft.imageAssetId ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={withBase(`/api/assets/${draft.imageAssetId}/preview`)} alt="" className="absolute inset-0 h-full w-full object-cover" />
              ) : (
                <span className="flex flex-col items-center gap-1 p-3">
                  <Upload className="size-4" />
                  {busy === "upload" ? "Uploading…" : "Example flyer (optional)"}
                </span>
              )}
              <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            </label>
            <Button variant="outline" size="sm" className="w-full" onClick={analyze} disabled={!draft.imageAssetId || !aiEnabled || busy !== null}>
              <Sparkles /> {busy === "analyze" ? "Analysing…" : "Analyse with Claude"}
            </Button>
            {!aiEnabled && <p className="text-[11px] text-muted-foreground">Add an ANTHROPIC_API_KEY to analyse uploads automatically.</p>}
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="List">
                <Choice
                  value={draft.kind ?? "inspire"}
                  onChange={(v) => setDraft({ ...draft, kind: v })}
                  options={[
                    { value: "avoid", label: "Avoid (AI tell)" },
                    { value: "inspire", label: "Inspire (traditional)" },
                  ]}
                />
              </Field>
              <Field label="Closest recipe">
                <Choice
                  value={draft.recipeId ?? "none"}
                  onChange={(v) => setDraft({ ...draft, recipeId: v === "none" ? null : v })}
                  options={[{ value: "none", label: "None" }, ...RECIPES.map((r) => ({ value: r.id, label: r.name }))]}
                />
              </Field>
            </div>
            <Field label="Title">
              <Input value={draft.title ?? ""} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder={draft.kind === "avoid" ? "e.g. Chrome lettering" : "e.g. 90s Chicago screenprints"} />
            </Field>
            <Field label="What you see">
              <Textarea value={draft.notes ?? ""} rows={3} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
            </Field>
            <Field label="Rules (one per line)">
              <Textarea value={traitsText} rows={6} onChange={(e) => setTraitsText(e.target.value)} placeholder={draft.kind === "avoid" ? "No chrome or bevel on type" : "Two spot colours plus paper"} />
            </Field>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!draft.title?.trim() || busy !== null}>
            {draft.id ? "Save" : "Add to rulebook"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
