"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, CalendarDays, Check, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Choice, Field } from "@/components/fields";
import { FlyerCanvas } from "@/components/flyer-canvas";
import { BriefForm } from "./brief-form";
import { useAiStatus, useAssets, useBand, useFetch } from "@/hooks/use-fetch";
import { eventLabel, eventToBrief, type CalendarEvent } from "@/lib/events";
import { useAssetImages } from "@/hooks/use-asset-images";
import { api, ApiError } from "@/lib/api";
import { directionToSpec, mockConcepts } from "@/lib/design";
import { formatDate, RECIPE_MAP } from "@/lib/recipes";
import { BriefSchema, type Brief, type FlyerSpec } from "@/lib/spec";
import { thumbnailBlob } from "@/lib/render/export";
import type { RenderReport, SourceImage } from "@/lib/render/render";
import type { Asset, Band, ConceptDirection, Flyer, FlyerVersion } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS = ["Gig details", "Design concept", "Layer in photo & logo"];

export function NewFlyer() {
  const router = useRouter();
  const eventId = useSearchParams().get("event");
  const eventQ = useFetch<{ event: CalendarEvent }>(eventId ? `/api/events/${eventId}` : null);
  const linkedEvent = eventQ.data?.event ?? null;
  const band = useBand();
  const photosQ = useAssets("photo");
  const logosQ = useAssets("logo");
  const ai = useAiStatus();
  const photos = useMemo(() => (photosQ.data ?? []).filter((p) => !p.archived), [photosQ.data]);
  const logos = useMemo(() => (logosQ.data ?? []).filter((l) => !l.archived), [logosQ.data]);
  const bandInfo: Band = useMemo(() => band.data?.band ?? { name: "", genre: "", hometown: "" }, [band.data]);

  const [step, setStep] = useState(0);
  const [brief, setBrief] = useState<Brief>(() => BriefSchema.parse({}));
  const [appliedEvent, setAppliedEvent] = useState<string | null>(null);
  if (linkedEvent && appliedEvent !== linkedEvent.id) {
    setAppliedEvent(linkedEvent.id);
    setBrief((b) => eventToBrief(linkedEvent, b));
  }
  const [concepts, setConcepts] = useState<ConceptDirection[]>([]);
  const [conceptSource, setConceptSource] = useState<"ai" | "builtin" | null>(null);
  const [loadingConcepts, setLoadingConcepts] = useState(false);
  const [showAssets, setShowAssets] = useState(false);
  const [chosen, setChosen] = useState<ConceptDirection | null>(null);
  const [creating, setCreating] = useState(false);
  const [report, setReport] = useState<RenderReport | null>(null);

  const specs = useMemo(
    () => concepts.map((c, i) => directionToSpec(c, brief, bandInfo, photos, logos, 1000 + i)),
    [concepts, brief, bandInfo, photos, logos],
  );
  const chosenSpec = useMemo(() => (chosen ? directionToSpec(chosen, brief, bandInfo, photos, logos, 4242) : null), [chosen, brief, bandInfo, photos, logos]);

  const assetIds = useMemo(() => {
    const ids = new Set<string>();
    for (const s of [...specs, ...(chosenSpec ? [chosenSpec] : [])]) for (const l of s.layers) if ((l.type === "photo" || l.type === "logo") && l.assetId) ids.add(l.assetId);
    return [...ids];
  }, [specs, chosenSpec]);
  const { images, verified, loading: imagesLoading } = useAssetImages([...photos, ...logos], step === 0 ? [] : assetIds);

  const generate = async () => {
    setLoadingConcepts(true);
    setConcepts([]);
    try {
      if (ai?.enabled) {
        try {
          const out = await api<{ concepts: ConceptDirection[] }>("/api/ai/concepts", { method: "POST", json: { brief, count: 3 } });
          setConcepts(out.concepts);
          setConceptSource("ai");
          return;
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 503)) toast.error(`Claude couldn't propose concepts (${e instanceof Error ? e.message : "error"}). Showing built-in directions.`);
        }
      }
      setConcepts(mockConcepts(brief, bandInfo, photos, logos, [], 3));
      setConceptSource("builtin");
    } finally {
      setLoadingConcepts(false);
    }
  };

  const create = async () => {
    if (!chosen || !chosenSpec) return;
    setCreating(true);
    try {
      const title = `${bandInfo.name || "Gig"} · ${brief.venue || "TBA"}${brief.date ? ` · ${formatDate(brief.date)}` : ""}`;
      const flyer = await api<Flyer>("/api/flyers", { method: "POST", json: { title, brief, eventId: linkedEvent?.id ?? null } });
      await saveVersion(flyer.id, chosenSpec, images, { label: `Concept: ${chosen.title}`, source: "concept", parentId: null });
      router.push(`/flyers/${flyer.id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not create the flyer");
      setCreating(false);
    }
  };

  const recipe = chosen ? RECIPE_MAP[chosen.recipeId] : null;
  const canNext = brief.date && brief.venue;
  const fidelityOk = report && report.fidelity.every((f) => f.uniform) && report.fidelity.every((f) => verified.get(f.assetId) !== false);

  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 py-8 sm:px-6">
      <ol className="mb-8 flex flex-wrap items-center gap-2 text-sm">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span className={cn("grid size-6 place-items-center rounded-full text-xs", i < step ? "bg-emerald-500/20 text-emerald-400" : i === step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
              {i < step ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span className={cn(i === step ? "font-medium" : "text-muted-foreground")}>{s}</span>
            {i < STEPS.length - 1 && <span className="mx-2 h-px w-8 bg-border" />}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="max-w-3xl space-y-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">What&apos;s the gig?</h1>
            <p className="mt-1 text-sm text-muted-foreground">Date and venue are required. Everything is typeset exactly as written; nothing is generated.</p>
          </div>
          {linkedEvent ? (
            <div className="flex items-center gap-2 rounded-md border border-border/60 bg-card/40 px-3 py-2 text-sm">
              <CalendarDays className="size-4 text-muted-foreground" />
              <span>
                Filed under <Link href={`/events/${linkedEvent.id}`} className="font-medium underline-offset-2 hover:underline">{eventLabel(linkedEvent)} · {linkedEvent.date}</Link>. Details below come from the calendar.
              </span>
            </div>
          ) : (
            !eventId && <p className="text-xs text-muted-foreground">This flyer is filed on the calendar under its date and venue; a gig is created if there isn&apos;t one yet.</p>
          )}
          {band.loading || photosQ.loading ? <Skeleton className="h-96" /> : <BriefForm brief={brief} onChange={setBrief} photos={photos} logos={logos} />}
          <div className="flex justify-end">
            <Button
              size="lg"
              disabled={!canNext || ai === null}
              onClick={() => {
                setStep(1);
                if (concepts.length === 0) void generate();
              }}
            >
              Propose concepts <ArrowRight />
            </Button>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Pick a design direction</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                Each concept is a layout from a real print tradition, shown as a wireframe so you judge structure, type and colour first. Your photo and logo go in at the next step.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Switch checked={showAssets} onCheckedChange={setShowAssets} /> Preview with our photo &amp; logo
              </label>
              <Button variant="outline" onClick={generate} disabled={loadingConcepts}>
                <RefreshCw className={cn(loadingConcepts && "animate-spin")} /> New concepts
              </Button>
            </div>
          </div>
          {conceptSource && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Sparkles className="size-3.5" />
              {conceptSource === "ai" ? `Directed by Claude (${ai?.model}) using your References rulebook.` : "Built-in art direction. Add an ANTHROPIC_API_KEY for Claude-directed concepts."}
            </p>
          )}
          <div className="grid gap-6 md:grid-cols-3">
            {loadingConcepts || specs.length === 0
              ? Array.from({ length: 3 }, (_, i) => (
                  <div key={i} className="space-y-3">
                    <Skeleton className="aspect-[2/3]" />
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-12" />
                  </div>
                ))
              : concepts.map((c, i) => (
                  <ConceptCard
                    key={`${c.recipeId}-${i}`}
                    concept={c}
                    spec={specs[i]}
                    images={images}
                    wireframe={!showAssets}
                    onPick={() => {
                      setChosen(c);
                      setStep(2);
                    }}
                  />
                ))}
          </div>
          <Button variant="ghost" onClick={() => setStep(0)}>
            <ArrowLeft /> Gig details
          </Button>
        </div>
      )}

      {step === 2 && chosen && chosenSpec && recipe && (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,560px)_1fr]">
          <div className="space-y-3">
            <FlyerCanvas spec={chosenSpec} images={images} resolution={560} onReport={setReport} className="rounded-sm" />
            <div className="flex items-center gap-2 text-xs">
              {imagesLoading ? (
                <span className="text-muted-foreground">Loading full-resolution originals…</span>
              ) : fidelityOk ? (
                <span className="flex items-center gap-1.5 text-emerald-400">
                  <ShieldCheck className="size-3.5" /> {report?.fidelity.length ? `${report.fidelity.length} original${report.fidelity.length > 1 ? "s" : ""} placed at uniform scale and verified` : "No photo or logo placed yet"}
                </span>
              ) : (
                <span className="text-destructive">An asset failed the fidelity check.</span>
              )}
            </div>
          </div>
          <div className="space-y-6">
            <div>
              <Badge variant="secondary">{recipe.name}</Badge>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight">{chosen.title}</h1>
              <p className="mt-1 text-sm text-muted-foreground">{chosen.rationale}</p>
            </div>
            <LayerControls concept={chosen} onChange={setChosen} photos={photos} logos={logos} />
            <div className="flex flex-wrap gap-3">
              <Button variant="ghost" onClick={() => setStep(1)}>
                <ArrowLeft /> Concepts
              </Button>
              <Button size="lg" onClick={create} disabled={creating || imagesLoading}>
                {creating ? "Creating…" : "Create flyer & open editor"} <ArrowRight />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ConceptCard({ concept, spec, images, wireframe, onPick }: { concept: ConceptDirection; spec: FlyerSpec; images: Map<string, SourceImage>; wireframe: boolean; onPick: () => void }) {
  const recipe = RECIPE_MAP[concept.recipeId];
  return (
    <div className="flex flex-col gap-3">
      <button onClick={onPick} className="group block rounded-sm text-left outline-none ring-ring focus-visible:ring-2">
        <FlyerCanvas spec={spec} images={images} wireframe={wireframe} resolution={420} className="rounded-sm transition-transform group-hover:-translate-y-0.5" />
      </button>
      <div className="flex items-center gap-2">
        <Badge variant="secondary">{recipe?.name}</Badge>
        <div className="flex gap-1">
          {[spec.palette.paper, spec.palette.ink, spec.palette.accent, spec.palette.accent2].map((c, i) => (
            <span key={i} className="size-3.5 rounded-sm border border-border" style={{ background: c }} />
          ))}
        </div>
        <span className="truncate text-xs text-muted-foreground">
          {spec.fonts.display} / {spec.fonts.text}
        </span>
      </div>
      <h3 className="font-medium">{concept.title}</h3>
      <p className="text-sm text-muted-foreground">{concept.rationale}</p>
      {concept.avoids && concept.avoids.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {concept.avoids.map((a) => (
            <span key={a} className="rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] text-red-300">
              avoids: {a}
            </span>
          ))}
        </div>
      )}
      <Button onClick={onPick} variant="outline" className="mt-auto">
        Use this direction <ArrowRight />
      </Button>
    </div>
  );
}

function LayerControls({ concept, onChange, photos, logos }: { concept: ConceptDirection; onChange: (c: ConceptDirection) => void; photos: Asset[]; logos: Asset[] }) {
  const recipe = RECIPE_MAP[concept.recipeId];
  const palettes = [...(concept.palette ? [concept.palette] : []), ...recipe.palettes];
  const currentPalette = concept.palette ?? recipe.palettes[(concept.paletteIndex ?? 0) % recipe.palettes.length];
  const currentFonts = concept.fonts ?? recipe.fontPairs[(concept.fontIndex ?? 0) % recipe.fontPairs.length];
  const tile = (active: boolean) => cn("relative size-16 shrink-0 overflow-hidden rounded-md border", active ? "border-primary ring-2 ring-primary/50" : "border-border hover:border-foreground/40");
  return (
    <div className="space-y-5">
      <Field label="Photo">
        {photos.length ? (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {photos.map((p) => (
              <button key={p.id} className={tile(concept.photoId === p.id)} onClick={() => onChange({ ...concept, photoId: p.id })} title={p.name}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/assets/${p.id}/preview`} alt={p.name} className="h-full w-full object-cover" />
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Upload photos in the Band kit to fill the frame.</p>
        )}
      </Field>
      <Field label="Logo">
        <div className="flex gap-2 overflow-x-auto pb-1">
          <button className={cn(tile(!concept.logoId), "grid place-items-center text-[11px] text-muted-foreground")} onClick={() => onChange({ ...concept, logoId: null })}>
            Typeset
          </button>
          {logos.map((l) => (
            <button key={l.id} className={cn(tile(concept.logoId === l.id), "checker")} onClick={() => onChange({ ...concept, logoId: l.id })} title={l.name}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/assets/${l.id}/preview`} alt={l.name} className="h-full w-full object-contain p-1.5" />
            </button>
          ))}
        </div>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Photo treatment" hint="Colour mapping only. Shapes are never altered.">
          <Choice
            value={(concept.treatment as string) ?? recipe.treatments[0]}
            onChange={(v) => onChange({ ...concept, treatment: v })}
            options={["original", "mono", "duotone", "tint", "threshold"].map((t) => ({ value: t, label: t === "threshold" ? "Photocopy (1-bit)" : t[0].toUpperCase() + t.slice(1) }))}
          />
        </Field>
        <Field label="Type pairing">
          <Choice
            value={`${currentFonts.display}|${currentFonts.text}`}
            onChange={(v) => {
              const [display, text] = v.split("|");
              onChange({ ...concept, fonts: { display, text } });
            }}
            options={[...new Map([currentFonts, ...recipe.fontPairs].map((f) => [`${f.display}|${f.text}`, f])).values()].map((f) => ({ value: `${f.display}|${f.text}`, label: `${f.display} / ${f.text}` }))}
          />
        </Field>
      </div>
      <Field label="Inks">
        <div className="flex flex-wrap gap-2">
          {palettes.map((p, i) => {
            const active = JSON.stringify(p) === JSON.stringify(currentPalette);
            return (
              <button key={i} onClick={() => onChange({ ...concept, palette: p })} className={cn("flex overflow-hidden rounded-md border", active ? "border-primary ring-2 ring-primary/50" : "border-border")}>
                {[p.paper, p.ink, p.accent, p.accent2].map((c, j) => (
                  <span key={j} className="h-8 w-6" style={{ background: c }} />
                ))}
              </button>
            );
          })}
        </div>
      </Field>
      {recipe.mirrorable && (
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={!!concept.mirror} onCheckedChange={(v) => onChange({ ...concept, mirror: v })} /> Mirror layout
        </label>
      )}
    </div>
  );
}

export async function saveVersion(
  flyerId: string,
  spec: FlyerSpec,
  images: Map<string, SourceImage>,
  meta: { label: string; source: FlyerVersion["source"]; parentId: string | null },
): Promise<FlyerVersion> {
  const form = new FormData();
  form.set("meta", JSON.stringify({ ...meta, spec, makeCurrent: true }));
  try {
    form.set("thumb", await thumbnailBlob(spec, images));
  } catch {
    // A missing thumbnail only affects the dashboard grid.
  }
  const res = await fetch(`/api/flyers/${flyerId}/versions`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Could not save version");
  return res.json();
}
