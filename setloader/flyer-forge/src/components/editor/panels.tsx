"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, ImageIcon, Info, Lock, LockOpen, Shapes, ShieldCheck, Sparkles, Type, Wand2, XCircle, Eye, EyeOff, Stamp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { FlyerCanvas } from "@/components/flyer-canvas";
import { LOCKABLE, type Lockable } from "@/lib/design";
import type { FlyerSpec, Layer } from "@/lib/spec";
import type { RenderReport, SourceImage } from "@/lib/render/render";
import type { Asset, Critique, CritiqueIssue, FlyerVersion } from "@/lib/types";
import { withBase } from "@/lib/session";
import { cn } from "@/lib/utils";

export function LayerIcon({ type, className }: { type: Layer["type"]; className?: string }) {
  const I = type === "text" ? Type : type === "photo" ? ImageIcon : type === "logo" ? Stamp : Shapes;
  return <I className={cn("size-3.5 shrink-0", className)} />;
}

export function LayersPanel({
  spec,
  selectedId,
  onSelect,
  onToggle,
  onAdd,
}: {
  spec: FlyerSpec;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onToggle: (id: string) => void;
  onAdd: (type: Layer["type"]) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-1">
        {(["text", "photo", "logo", "shape"] as const).map((t) => (
          <Button key={t} size="xs" variant="outline" onClick={() => onAdd(t)} className="capitalize">
            <LayerIcon type={t} /> {t}
          </Button>
        ))}
      </div>
      <ul className="space-y-0.5">
        {[...spec.layers].reverse().map((l) => (
          <li key={l.id}>
            <div
              role="button"
              tabIndex={0}
              onClick={() => onSelect(l.id)}
              onKeyDown={(e) => e.key === "Enter" && onSelect(l.id)}
              className={cn("group flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm", selectedId === l.id ? "bg-sky-500/15 text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground", l.hidden && "opacity-50")}
            >
              <LayerIcon type={l.type} />
              <span className="truncate">{l.type === "text" ? l.text.split("\n")[0] || l.name : l.name || l.type}</span>
              <button
                className="ml-auto opacity-0 group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggle(l.id);
                }}
                aria-label={l.hidden ? "Show layer" : "Hide layer"}
              >
                {l.hidden ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
              </button>
            </div>
          </li>
        ))}
        <li>
          <button onClick={() => onSelect(null)} className={cn("flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm", selectedId === null ? "bg-sky-500/15" : "text-muted-foreground hover:bg-muted/60")}>
            <span className="size-3.5 rounded-sm border border-border" style={{ background: spec.palette.paper }} /> Background &amp; inks
          </button>
        </li>
      </ul>
    </div>
  );
}

export function VersionsPanel({ flyerId, versions, currentId, onOpen }: { flyerId: string; versions: FlyerVersion[]; currentId: string | null; onOpen: (v: FlyerVersion) => void }) {
  const index = new Map(versions.map((v, i) => [v.id, i + 1]));
  return (
    <ul className="space-y-1.5">
      {[...versions].reverse().map((v) => (
        <li key={v.id}>
          <button onClick={() => onOpen(v)} className={cn("flex w-full gap-2.5 rounded-md border p-1.5 text-left transition-colors", v.id === currentId ? "border-sky-500/60 bg-sky-500/10" : "border-transparent hover:bg-muted/60")}>
            <div className="w-11 shrink-0 overflow-hidden rounded-sm bg-muted">
              {v.hasThumb && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={withBase(`/api/flyers/${flyerId}/versions/${v.id}/thumb`)} alt="" className="w-full" loading="lazy" />
              )}
            </div>
            <div className="min-w-0 text-xs">
              <div className="font-medium text-foreground">
                v{index.get(v.id)} <span className="font-normal text-muted-foreground">· {v.source.replace("-", " ")}</span>
              </div>
              <div className="line-clamp-2 text-muted-foreground">{v.label}</div>
              {v.parentId && <div className="text-[10px] text-muted-foreground/70">from v{index.get(v.parentId)}</div>}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

export interface Variation {
  spec: FlyerSpec;
  label: string;
  source: FlyerVersion["source"];
  note?: string;
}

export function GeneratePanel({
  aiEnabled,
  busy,
  locks,
  onLocks,
  onAsk,
  onEvolve,
  onConcepts,
  variations,
  images,
  onUse,
  onClear,
}: {
  aiEnabled: boolean;
  busy: string | null;
  locks: Lockable[];
  onLocks: (l: Lockable[]) => void;
  onAsk: (instruction: string) => void;
  onEvolve: () => void;
  onConcepts: () => void;
  variations: Variation[];
  images: Map<string, SourceImage>;
  onUse: (v: Variation) => void;
  onClear: () => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium">
          <Wand2 className="size-4" /> Iterate
        </h3>
        <Textarea
          value={text}
          rows={3}
          onChange={(e) => setText(e.target.value)}
          placeholder={aiEnabled ? "Make the date much bigger and move the info block to the left; try the individual shot of Sam" : "e.g. bigger date · black and white photo · swap photo · new palette · less grain · mirror"}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && text.trim()) onAsk(text.trim());
          }}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] text-muted-foreground">{aiEnabled ? "Claude edits the layout spec; assets stay untouched." : "Built-in editor understands common requests."}</span>
          <Button size="sm" onClick={() => text.trim() && onAsk(text.trim())} disabled={!text.trim() || busy !== null}>
            {busy === "ask" ? "Applying…" : "Apply"}
          </Button>
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles className="size-4" /> Evolve
        </h3>
        <p className="text-xs text-muted-foreground">Four variations of this version. Lock what you like.</p>
        <div className="flex flex-wrap gap-1.5">
          {LOCKABLE.map((k) => {
            const on = locks.includes(k);
            return (
              <button
                key={k}
                onClick={() => onLocks(on ? locks.filter((x) => x !== k) : [...locks, k])}
                className={cn("flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs capitalize", on ? "border-amber-400/60 bg-amber-400/10 text-amber-300" : "border-border text-muted-foreground hover:text-foreground")}
              >
                {on ? <Lock className="size-3" /> : <LockOpen className="size-3" />} {k}
              </button>
            );
          })}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button size="sm" variant="outline" onClick={onEvolve} disabled={busy !== null || locks.length === LOCKABLE.length}>
            {busy === "evolve" ? "Evolving…" : "Evolve ×4"}
          </Button>
          <Button size="sm" variant="outline" onClick={onConcepts} disabled={busy !== null}>
            {busy === "concepts" ? "Thinking…" : "Fresh concepts"}
          </Button>
        </div>
      </section>

      {variations.length > 0 && (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">Variations</h3>
            <Button size="xs" variant="ghost" onClick={onClear}>
              Clear
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {variations.map((v, i) => (
              <div key={i} className="space-y-1.5">
                <button onClick={() => onUse(v)} className="block w-full rounded-sm ring-sky-500 hover:ring-2">
                  <FlyerCanvas spec={v.spec} images={images} resolution={220} className="rounded-sm" />
                </button>
                <p className="line-clamp-2 text-[11px] text-muted-foreground">{v.label}</p>
                <Button size="xs" variant="secondary" className="w-full" onClick={() => onUse(v)}>
                  Use as new version
                </Button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const SEV: Record<CritiqueIssue["severity"], { icon: typeof Circle; cls: string }> = {
  pass: { icon: CheckCircle2, cls: "text-emerald-400" },
  info: { icon: Info, cls: "text-sky-400" },
  warn: { icon: AlertTriangle, cls: "text-amber-400" },
  fail: { icon: XCircle, cls: "text-red-400" },
};

export function CritiqueView({ critique, onFix, busy }: { critique: Critique; onFix?: (fix: string) => void; busy: boolean }) {
  const order = { fail: 0, warn: 1, info: 2, pass: 3 } as const;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className={cn("grid size-12 place-items-center rounded-full border-2 text-sm font-semibold tabular-nums", critique.score >= 85 ? "border-emerald-400 text-emerald-400" : critique.score >= 65 ? "border-amber-400 text-amber-400" : "border-red-400 text-red-400")}>
          {critique.score}
        </div>
        <div className="min-w-0">
          <Badge variant="outline" className="mb-1">
            {critique.source === "ai" ? "Claude critique" : "Automated checks"}
          </Badge>
          <p className="text-xs text-muted-foreground">{critique.summary}</p>
        </div>
      </div>
      <ul className="space-y-2">
        {[...critique.issues]
          .sort((a, b) => order[a.severity] - order[b.severity])
          .map((i, n) => {
            const S = SEV[i.severity];
            return (
              <li key={n} className="flex gap-2 text-xs">
                <S.icon className={cn("mt-0.5 size-3.5 shrink-0", S.cls)} />
                <div className="min-w-0 space-y-1">
                  <div>
                    <span className="font-medium text-foreground">{i.area}.</span> <span className="text-muted-foreground">{i.note}</span>
                  </div>
                  {i.fix && onFix && i.severity !== "pass" && (
                    <button className="text-sky-400 hover:underline disabled:opacity-50" disabled={busy} onClick={() => onFix(i.fix!)}>
                      Apply: {i.fix}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
      </ul>
    </div>
  );
}

export function FidelityList({ report, assets, verified }: { report: RenderReport | null; assets: Asset[]; verified: Map<string, boolean> }) {
  if (!report) return null;
  if (!report.fidelity.length) return <p className="text-xs text-muted-foreground">No photos or logos placed.</p>;
  return (
    <ul className="space-y-1.5">
      {report.fidelity.map((f) => {
        const a = assets.find((x) => x.id === f.assetId);
        const ok = f.uniform && verified.get(f.assetId) !== false;
        return (
          <li key={f.layerId} className="flex items-start gap-2 text-xs">
            {ok ? <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-400" /> : <XCircle className="mt-0.5 size-3.5 shrink-0 text-red-400" />}
            <div className="min-w-0">
              <div className="truncate text-foreground">
                {a?.name || f.kind} <span className="text-muted-foreground">({f.kind})</span>
              </div>
              <div className="font-mono text-[10px] text-muted-foreground">
                scale x {f.scaleX.toFixed(4)} · y {f.scaleY.toFixed(4)} · {Math.round(f.visibleFraction * 100)}% visible ·{" "}
                {verified.get(f.assetId) ? "sha256 ✓" : verified.has(f.assetId) ? "sha256 ✗" : "verifying"}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
