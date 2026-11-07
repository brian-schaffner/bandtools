"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { AlertTriangle, ArrowLeft, CalendarDays, Download, FileText, Pencil, Redo2, Save, Sparkles, Undo2 } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Choice, Field } from "@/components/fields";
import { BriefForm } from "@/components/flyers/brief-form";
import { saveVersion } from "@/components/flyers/new-flyer";
import { CanvasStage } from "./canvas-stage";
import { Inspector } from "./inspector";
import { CritiqueView, FidelityList, GeneratePanel, LayersPanel, VersionsPanel, type Variation } from "./panels";
import { useAiStatus, useAssets, useBand, useFetch } from "@/hooks/use-fetch";
import { briefMismatches, eventLabel, eventToBrief, type CalendarEvent } from "@/lib/events";
import { useAssetImages } from "@/hooks/use-asset-images";
import { api, ApiError } from "@/lib/api";
import { adaptFormat, directionToSpec, evolve, localEdit, mockConcepts, type Lockable } from "@/lib/design";
import { FORMAT_IDS, FORMATS, type Brief, type FlyerSpec, type FormatId, type Layer } from "@/lib/spec";
import { runChecks } from "@/lib/render/checks";
import { critiqueImage, exportPng, exportPrintPdf, FidelityError } from "@/lib/render/export";
import type { RenderReport } from "@/lib/render/render";
import type { Band, ConceptDirection, Critique, Flyer, FlyerVersion } from "@/lib/types";

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "flyer";

export function FlyerEditor() {
  const { id } = useParams<{ id: string }>();
  const band = useBand();
  const photosQ = useAssets("photo");
  const logosQ = useAssets("logo");
  const ai = useAiStatus();
  const photos = useMemo(() => photosQ.data ?? [], [photosQ.data]);
  const logos = useMemo(() => logosQ.data ?? [], [logosQ.data]);
  const bandInfo: Band = useMemo(() => band.data?.band ?? { name: "", genre: "", hometown: "" }, [band.data]);

  const [flyer, setFlyer] = useState<Flyer | null>(null);
  const [versions, setVersions] = useState<FlyerVersion[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [base, setBase] = useState<FlyerVersion | null>(null);
  const [spec, setSpec] = useState<FlyerSpec | null>(null);
  const [past, setPast] = useState<FlyerSpec[]>([]);
  const [future, setFuture] = useState<FlyerSpec[]>([]);
  const dragSnapshot = useRef<FlyerSpec | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [locks, setLocks] = useState<Lockable[]>([]);
  const [variations, setVariations] = useState<Variation[]>([]);
  const [checks, setChecks] = useState<Critique | null>(null);
  const [aiCritique, setAiCritique] = useState<Critique | null>(null);
  const [report, setReport] = useState<RenderReport | null>(null);
  const [tab, setTab] = useState("edit");
  const [briefOpen, setBriefOpen] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const eventQ = useFetch<{ event: CalendarEvent }>(flyer?.eventId ? `/api/events/${flyer.eventId}` : null);
  const linkedEvent = eventQ.data?.event ?? null;

  useEffect(() => {
    api<{ flyer: Flyer; versions: FlyerVersion[] }>(`/api/flyers/${id}`)
      .then(({ flyer, versions }) => {
        setFlyer(flyer);
        setVersions(versions);
        const cur = versions.find((v) => v.id === flyer.currentVersionId) ?? versions[versions.length - 1] ?? null;
        setBase(cur);
        setSpec(cur ? clone(cur.spec) : null);
        setAiCritique(cur?.critique?.source === "ai" ? cur.critique : null);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Could not load flyer"));
  }, [id]);

  const assetIds = useMemo(() => {
    const ids = new Set<string>();
    for (const s of [spec, ...variations.map((v) => v.spec)]) for (const l of s?.layers ?? []) if ((l.type === "photo" || l.type === "logo") && l.assetId) ids.add(l.assetId);
    return [...ids];
  }, [spec, variations]);
  const { images, verified, loading: imagesLoading, error: imagesError } = useAssetImages([...photos, ...logos], assetIds);

  const dirty = !!spec && !!base && JSON.stringify(spec) !== JSON.stringify(base.spec);

  // ---------- spec mutations ----------
  const commit = useCallback((next: FlyerSpec) => {
    setSpec((cur) => {
      if (cur) setPast((p) => [...p.slice(-60), cur]);
      return next;
    });
    setFuture([]);
  }, []);

  const patchLayer = (layerId: string, patch: Partial<Layer>, live = false) => {
    if (!spec) return;
    const next = { ...spec, layers: spec.layers.map((l) => (l.id === layerId ? ({ ...l, ...patch } as Layer) : l)) };
    if (live) {
      dragSnapshot.current ??= spec;
      setSpec(next);
    } else commit(next);
  };

  const endDrag = () => {
    if (dragSnapshot.current) {
      const snap = dragSnapshot.current;
      setPast((p) => [...p.slice(-60), snap]);
      setFuture([]);
      dragSnapshot.current = null;
    }
  };

  const undo = useCallback(() => {
    setPast((p) => {
      if (!p.length) return p;
      const prev = p[p.length - 1];
      setSpec((cur) => {
        if (cur) setFuture((f) => [cur, ...f]);
        return prev;
      });
      return p.slice(0, -1);
    });
  }, []);
  const redo = useCallback(() => {
    setFuture((f) => {
      if (!f.length) return f;
      const next = f[0];
      setSpec((cur) => {
        if (cur) setPast((p) => [...p, cur]);
        return next;
      });
      return f.slice(1);
    });
  }, []);

  // ---------- versions ----------
  const persist = useCallback(
    async (next: FlyerSpec, label: string, source: FlyerVersion["source"]) => {
      if (!flyer) return null;
      try {
        const v = await saveVersion(flyer.id, next, images, { label, source, parentId: base?.id ?? null });
        setVersions((vs) => [...vs, v]);
        setBase(v);
        setSpec(clone(v.spec));
        setAiCritique(null);
        return v;
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Could not save version");
        return null;
      }
    },
    [flyer, images, base],
  );

  const saveManual = useCallback(async () => {
    if (!spec || !dirty) return;
    setBusy("save");
    const v = await persist(spec, "Manual edits", "manual");
    setBusy(null);
    if (v) toast.success("Saved as a new version");
  }, [spec, dirty, persist]);

  const openVersion = async (v: FlyerVersion) => {
    if (!flyer) return;
    if (dirty && !confirm("Discard unsaved changes and open this version?")) return;
    setBase(v);
    setSpec(clone(v.spec));
    setPast([]);
    setFuture([]);
    setSelectedId(null);
    setAiCritique(v.critique?.source === "ai" ? v.critique : null);
    await api(`/api/flyers/${flyer.id}`, { method: "PATCH", json: { currentVersionId: v.id } }).catch(() => undefined);
  };

  // ---------- keyboard ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement).isContentEditable;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void saveManual();
        return;
      }
      if (typing) return;
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      } else if ((e.key === "Delete" || e.key === "Backspace") && selectedId && spec) {
        commit({ ...spec, layers: spec.layers.filter((l) => l.id !== selectedId) });
        setSelectedId(null);
      } else if (e.key.startsWith("Arrow") && selectedId && spec) {
        e.preventDefault();
        const step = e.shiftKey ? 0.01 : 0.002;
        const l = spec.layers.find((x) => x.id === selectedId)!;
        const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key] ?? [0, 0];
        patchLayer(selectedId, { x: l.x + d[0], y: l.y + d[1] });
      } else if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // ---------- automated checks ----------
  useEffect(() => {
    if (!spec || !flyer || imagesLoading) return;
    const t = setTimeout(() => {
      runChecks(spec, flyer.brief, images, verified)
        .then(setChecks)
        .catch(() => undefined);
    }, 500);
    return () => clearTimeout(t);
  }, [spec, flyer, images, verified, imagesLoading]);

  // ---------- generate ----------
  const ask = async (instruction: string) => {
    if (!spec) return;
    setBusy("ask");
    try {
      if (ai?.enabled) {
        try {
          const out = await api<{ note: string; spec: FlyerSpec }>("/api/ai/edit", { method: "POST", json: { spec, instruction } });
          commit(out.spec);
          await persist(out.spec, out.note, "ai-edit");
          toast.success(out.note);
          return;
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 503)) {
            toast.error(e instanceof Error ? e.message : "Claude edit failed");
            return;
          }
        }
      }
      const out = localEdit(spec, instruction, photos);
      if (!out) {
        toast.message("Couldn't interpret that without Claude", { description: "Try: bigger date · black and white photo · swap photo · new palette · mirror · less grain · different fonts" });
        return;
      }
      commit(out.spec);
      await persist(out.spec, out.note, "edit");
      toast.success(out.note);
    } finally {
      setBusy(null);
    }
  };

  const runEvolve = () => {
    if (!spec) return;
    setBusy("evolve");
    try {
      const out = evolve(spec, locks, 4, photos.filter((p) => !p.archived));
      setVariations(out.map((o) => ({ ...o, source: "evolve" as const })));
      setTab("generate");
    } finally {
      setBusy(null);
    }
  };

  const freshConcepts = async () => {
    if (!flyer || !spec) return;
    setBusy("concepts");
    const brief = { ...flyer.brief, format: spec.format };
    try {
      let concepts: ConceptDirection[] | null = null;
      if (ai?.enabled) {
        try {
          concepts = (await api<{ concepts: ConceptDirection[] }>("/api/ai/concepts", { method: "POST", json: { brief, count: 4, exclude: [] } })).concepts;
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 503)) toast.error(`Claude concepts failed; using built-in (${e instanceof Error ? e.message : ""})`);
        }
      }
      concepts ??= mockConcepts(brief, bandInfo, photos, logos, [], 4);
      setVariations(
        concepts.map((c, i) => ({
          spec: directionToSpec(c, brief, bandInfo, photos, logos, Date.now() + i),
          label: `Concept: ${c.title}. ${c.rationale}`,
          source: "concept" as const,
        })),
      );
      setTab("generate");
    } finally {
      setBusy(null);
    }
  };

  const useVariation = async (v: Variation) => {
    commit(v.spec);
    const saved = await persist(v.spec, v.label.split(". ")[0], v.source);
    if (saved) toast.success("Added as a new version");
  };

  const critique = async () => {
    if (!spec || !flyer) return;
    setBusy("critique");
    try {
      const image = await critiqueImage(spec, images);
      const out = await api<Critique>("/api/ai/critique", {
        method: "POST",
        json: { image, brief: flyer.brief, checks: (checks?.issues ?? []).filter((i) => i.severity !== "pass").map((i) => `${i.area}: ${i.note}`) },
      });
      setAiCritique(out);
      if (base && !dirty) await api(`/api/flyers/${flyer.id}/versions/${base.id}`, { method: "PATCH", json: { critique: out } }).catch(() => undefined);
    } catch (e) {
      toast.error(e instanceof ApiError && e.status === 503 ? "Add an ANTHROPIC_API_KEY to get Claude's critique." : e instanceof Error ? e.message : "Critique failed");
    } finally {
      setBusy(null);
    }
  };

  // ---------- export ----------
  const doExport = async (kind: "png" | "pdf") => {
    if (!spec || !flyer) return;
    setBusy(`export-${kind}`);
    try {
      if (kind === "png") await exportPng(spec, images, slug(flyer.title));
      else await exportPrintPdf(spec, images, slug(flyer.title));
      toast.success("Exported");
    } catch (e) {
      toast.error(e instanceof FidelityError ? e.message : e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(null);
    }
  };

  const adapt = async (format: FormatId) => {
    if (!spec || !flyer) return;
    const next = adaptFormat(spec, format, flyer.brief, bandInfo, photos, logos);
    commit(next);
    await persist(next, `Adapted to ${FORMATS[format].label}`, "manual");
    toast.success(`Re-laid out for ${FORMATS[format].label}`);
  };

  const addLayer = (type: Layer["type"]) => {
    if (!spec) return;
    const lid = `${type}-${Date.now().toString(36)}`;
    const common = { id: lid, rotation: 0, opacity: 1, blend: "normal" as const, hidden: false };
    let layer: Layer;
    if (type === "text")
      layer = { ...common, type, name: "text", role: "custom", text: "New text", font: spec.fonts.text, weight: 400, size: 0.04, color: "$ink", align: "left", valign: "top", transform: "none", tracking: 0, leading: 1.1, fill: false, misregister: null, x: 0.1, y: 0.45, w: 0.8, h: 0.08 };
    else if (type === "shape") layer = { ...common, type, name: "block", shape: "rect", fill: "$accent", rays: 24, x: 0.1, y: 0.4, w: 0.3, h: 0.1 };
    else if (type === "photo") {
      const p = photos.find((x) => !x.archived) ?? null;
      layer = { ...common, type, name: "photo", assetId: p?.id ?? null, fit: "cover", zoom: 1, focusX: p?.focalX ?? 0.5, focusY: p?.focalY ?? 0.4, mask: "rect", treatment: { mode: "original", dark: "$ink", light: "$paper", contrast: 0, brightness: 0, threshold: 0.5 }, misregister: null, x: 0.2, y: 0.3, w: 0.6, h: 0.3 };
    } else {
      const lg = logos.find((x) => !x.archived) ?? null;
      layer = { ...common, type, name: "logo", assetId: lg?.id ?? null, recolor: null, recolorMode: "tone", align: "center", backdrop: "auto", x: 0.2, y: 0.05, w: 0.6, h: 0.12 };
    }
    commit({ ...spec, layers: [...spec.layers, layer] });
    setSelectedId(lid);
    setTab("edit");
  };

  const moveLayer = (dir: -1 | 1) => {
    if (!spec || !selectedId) return;
    const i = spec.layers.findIndex((l) => l.id === selectedId);
    const j = i + dir;
    if (j < 0 || j >= spec.layers.length) return;
    const layers = [...spec.layers];
    [layers[i], layers[j]] = [layers[j], layers[i]];
    commit({ ...spec, layers });
  };

  const saveBrief = async (brief: Brief, relayout: boolean) => {
    if (!flyer) return;
    try {
      const updated = await api<Flyer>(`/api/flyers/${flyer.id}`, { method: "PATCH", json: { brief } });
      setFlyer(updated);
      if (linkedEvent && briefMismatches(linkedEvent, brief).length) {
        const { date, venue, city, address, doors, showTime, endTime, price, ages, support, tickets } = brief;
        const event = await api<CalendarEvent>(`/api/events/${linkedEvent.id}`, {
          method: "PATCH",
          json: { date, venue, city, address, doors, showTime, endTime, price, ages, support: support.map((x) => x.trim()).filter(Boolean), tickets, ...(brief.headline ? { title: brief.headline } : {}) },
        });
        eventQ.setData({ event });
      }
      setBriefOpen(false);
      if (relayout && spec) {
        const next = adaptFormat(spec, spec.format, brief, bandInfo, photos, logos);
        commit(next);
        await persist(next, "Re-laid out with updated gig details", "manual");
      }
      toast.success(linkedEvent ? "Gig details saved to the flyer and the calendar" : "Gig details saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
    }
  };

  // ---------- render ----------
  if (loadError)
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center">
        <p className="text-sm text-destructive">{loadError}</p>
        <Link href="/" className={buttonVariants({ variant: "link" })}>
          Back to flyers
        </Link>
      </div>
    );
  if (!flyer || (!spec && versions.length > 0))
    return (
      <div className="mx-auto grid w-full max-w-[1500px] gap-6 px-4 py-6 lg:grid-cols-[260px_1fr_360px]">
        <Skeleton className="h-96" />
        <Skeleton className="mx-auto aspect-[2/3] w-full max-w-xl" />
        <Skeleton className="h-96" />
      </div>
    );
  if (!spec)
    return (
      <div className="mx-auto max-w-md px-6 py-20 text-center text-sm text-muted-foreground">
        This flyer has no designs yet.{" "}
        <Link href="/flyers/new" className="text-foreground underline">
          Start from concepts
        </Link>
      </div>
    );

  const selected = spec.layers.find((l) => l.id === selectedId) ?? null;
  const calendarDiff = linkedEvent ? briefMismatches(linkedEvent, flyer.brief) : [];
  const fidelityOk = !!report && report.fidelity.every((f) => f.uniform) && report.fidelity.every((f) => verified.get(f.assetId) !== false) && !report.missingAssets.length;

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 py-4 sm:px-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link href="/" className={buttonVariants({ variant: "ghost", size: "icon-sm" })} aria-label="Back">
          <ArrowLeft />
        </Link>
        <Input
          defaultValue={flyer.title}
          onBlur={(e) => {
            const title = e.target.value.trim();
            if (title && title !== flyer.title) void api<Flyer>(`/api/flyers/${flyer.id}`, { method: "PATCH", json: { title } }).then(setFlyer);
          }}
          className="h-8 max-w-md border-transparent bg-transparent text-base font-medium hover:border-input"
        />
        <Button variant="ghost" size="sm" onClick={() => setBriefOpen(true)}>
          <Pencil /> Gig details
        </Button>
        {linkedEvent && (
          <Link href={`/events/${linkedEvent.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })} title="Open this gig on the calendar">
            <CalendarDays /> <span className="max-w-48 truncate">{eventLabel(linkedEvent)} · {linkedEvent.date}</span>
          </Link>
        )}
        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="ghost" size="icon-sm" onClick={undo} disabled={!past.length} title="Undo (⌘Z)">
            <Undo2 />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={redo} disabled={!future.length} title="Redo (⇧⌘Z)">
            <Redo2 />
          </Button>
          <Button size="sm" variant={dirty ? "default" : "outline"} onClick={saveManual} disabled={!dirty || busy !== null}>
            <Save /> {dirty ? "Save version" : "Saved"}
          </Button>
        </div>
      </div>

      {calendarDiff.length > 0 && linkedEvent && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
          <AlertTriangle className="size-4 shrink-0 text-amber-300" />
          <span className="min-w-0 flex-1">
            The calendar has different details: {calendarDiff.map((d) => `${d.label} “${d.event}” (flyer: “${d.flyer}”)`).join(" · ")}
          </span>
          <Button size="sm" variant="outline" onClick={() => saveBrief(eventToBrief(linkedEvent, flyer.brief), true)}>
            Update flyer from calendar
          </Button>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)_360px]">
        <aside className="order-2 space-y-6 lg:order-1">
          <section>
            <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Layers</h2>
            <LayersPanel spec={spec} selectedId={selectedId} onSelect={(lid) => { setSelectedId(lid); setTab("edit"); }} onToggle={(lid) => patchLayer(lid, { hidden: !spec.layers.find((l) => l.id === lid)?.hidden })} onAdd={addLayer} />
          </section>
          <section>
            <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Versions · {versions.length}</h2>
            <div className="max-h-[420px] overflow-y-auto pr-1">
              <VersionsPanel flyerId={flyer.id} versions={versions} currentId={base?.id ?? null} onOpen={openVersion} />
            </div>
          </section>
        </aside>

        <div className="order-1 lg:order-2">
          <div className="mx-auto max-w-[620px] space-y-2">
            <CanvasStage
              spec={spec}
              images={images}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onLayerChange={(lid, p) => patchLayer(lid, p, true)}
              onCommit={endDrag}
              onReport={setReport}
              wireframe={wireframe}
            />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>
                {FORMATS[spec.format].label} · {spec.fonts.display} / {spec.fonts.text}
                {imagesLoading && " · loading originals…"}
                {imagesError && <span className="text-destructive"> · {imagesError}</span>}
              </span>
              <label className="flex items-center gap-1.5">
                <Switch checked={wireframe} onCheckedChange={setWireframe} /> Concept wireframe
              </label>
            </div>
            <p className={fidelityOk ? "text-xs text-emerald-400" : "text-xs text-amber-400"}>
              {fidelityOk ? `Fidelity: ${report?.fidelity.length ?? 0} original${report?.fidelity.length === 1 ? "" : "s"} at uniform scale, byte-verified.` : imagesLoading ? "Verifying originals…" : "Fidelity check needs attention: see Review."}
            </p>
          </div>
        </div>

        <aside className="order-3">
          <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
            <TabsList className="w-full">
              <TabsTrigger value="edit">Edit</TabsTrigger>
              <TabsTrigger value="generate">Generate</TabsTrigger>
              <TabsTrigger value="review">
                Review
                {checks && <span className="ml-1 font-mono text-[10px] text-muted-foreground">{checks.score}</span>}
              </TabsTrigger>
              <TabsTrigger value="export">Export</TabsTrigger>
            </TabsList>
            <div className="mt-4 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
              <TabsContent value="edit">
                <Inspector
                  spec={spec}
                  layer={selected}
                  photos={photos.filter((p) => !p.archived)}
                  logos={logos.filter((l) => !l.archived)}
                  onLayer={(p) => selected && patchLayer(selected.id, p)}
                  onSpec={commit}
                  onDelete={() => {
                    if (!selected) return;
                    commit({ ...spec, layers: spec.layers.filter((l) => l.id !== selected.id) });
                    setSelectedId(null);
                  }}
                  onMove={moveLayer}
                />
              </TabsContent>
              <TabsContent value="generate">
                <GeneratePanel
                  aiEnabled={!!ai?.enabled}
                  busy={busy}
                  locks={locks}
                  onLocks={setLocks}
                  onAsk={ask}
                  onEvolve={runEvolve}
                  onConcepts={freshConcepts}
                  variations={variations}
                  images={images}
                  onUse={useVariation}
                  onClear={() => setVariations([])}
                />
              </TabsContent>
              <TabsContent value="review" className="space-y-6">
                {checks ? <CritiqueView critique={checks} onFix={ask} busy={busy !== null} /> : <Skeleton className="h-40" />}
                <div className="space-y-3 border-t border-border/60 pt-4">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-medium">Art director&apos;s critique</h3>
                    <Button size="sm" variant="outline" onClick={critique} disabled={busy !== null || !ai?.enabled}>
                      <Sparkles /> {busy === "critique" ? "Looking…" : aiCritique ? "Re-run" : "Ask Claude"}
                    </Button>
                  </div>
                  {!ai?.enabled && <p className="text-xs text-muted-foreground">Add an ANTHROPIC_API_KEY to get a vision critique against your References rulebook.</p>}
                  {aiCritique && <CritiqueView critique={aiCritique} onFix={ask} busy={busy !== null} />}
                </div>
              </TabsContent>
              <TabsContent value="export" className="space-y-6">
                <section className="space-y-2">
                  <h3 className="text-sm font-medium">Download</h3>
                  <Button className="w-full justify-start" variant="outline" onClick={() => doExport("png")} disabled={busy !== null || !fidelityOk}>
                    <Download /> PNG · {FORMATS[spec.format].print ? `${FORMATS[spec.format].print!.w * 300}×${FORMATS[spec.format].print!.h * 300} px (300 dpi)` : `${FORMATS[spec.format].w}×${FORMATS[spec.format].h} px`}
                  </Button>
                  {FORMATS[spec.format].print && (
                    <Button className="w-full justify-start" variant="outline" onClick={() => doExport("pdf")} disabled={busy !== null || !fidelityOk}>
                      <FileText /> Print PDF · ⅛&quot; bleed + crop marks
                    </Button>
                  )}
                  {!fidelityOk && !imagesLoading && <p className="text-xs text-amber-400">Export is blocked until every photo and logo passes the fidelity check.</p>}
                </section>
                <section className="space-y-2">
                  <h3 className="text-sm font-medium">Same design, other size</h3>
                  <p className="text-xs text-muted-foreground">Re-lays out this design&apos;s recipe, inks, type and photo for another format, as a new version.</p>
                  <Field label="Format">
                    <Choice value={spec.format} onChange={(f) => f !== spec.format && adapt(f)} options={FORMAT_IDS.map((f) => ({ value: f, label: FORMATS[f].label }))} />
                  </Field>
                </section>
                <section className="space-y-2">
                  <h3 className="text-sm font-medium">Fidelity report</h3>
                  <FidelityList report={report} assets={[...photos, ...logos]} verified={verified} />
                </section>
              </TabsContent>
            </div>
          </Tabs>
        </aside>
      </div>

      <BriefDialog open={briefOpen} onOpenChange={setBriefOpen} brief={flyer.brief} onSave={saveBrief} />
    </div>
  );
}

function BriefDialog({ open, onOpenChange, brief, onSave }: { open: boolean; onOpenChange: (o: boolean) => void; brief: Brief; onSave: (b: Brief, relayout: boolean) => void }) {
  const [draft, setDraft] = useState(brief);
  const [prev, setPrev] = useState(brief);
  if (prev !== brief) {
    setPrev(brief);
    setDraft(brief);
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Gig details</DialogTitle>
          <DialogDescription>Saving keeps your current design. Re-lay out to rebuild the text from these details with the same recipe, inks and photo.</DialogDescription>
        </DialogHeader>
        <BriefForm brief={draft} onChange={setDraft} photos={[]} logos={[]} showAssets={false} />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onSave(draft, false)}>
            Save details only
          </Button>
          <Button onClick={() => onSave(draft, true)}>Save &amp; re-lay out</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
