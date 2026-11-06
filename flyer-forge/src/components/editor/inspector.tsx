"use client";

import { ArrowDown, ArrowUp, Eye, EyeOff, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Choice, ColorField, Field, NumberSlider } from "@/components/fields";
import { FONT_IDS, FONTS, type FontId } from "@/lib/fonts";
import { setFonts } from "@/lib/design";
import { TEXT_ROLES, type FlyerSpec, type Layer, type LogoLayer, type PhotoLayer, type ShapeLayer, type TextLayer, type Texture } from "@/lib/spec";
import type { Asset } from "@/lib/types";
import { cn } from "@/lib/utils";

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);
const pct = (v: number) => `${Math.round(v * 100)}%`;

export function Inspector({
  spec,
  layer,
  photos,
  logos,
  onLayer,
  onSpec,
  onDelete,
  onMove,
}: {
  spec: FlyerSpec;
  layer: Layer | null;
  photos: Asset[];
  logos: Asset[];
  onLayer: (patch: Partial<Layer>) => void;
  onSpec: (s: FlyerSpec) => void;
  onDelete: () => void;
  onMove: (dir: -1 | 1) => void;
}) {
  if (!layer) return <BackgroundInspector spec={spec} onSpec={onSpec} />;
  const tokens = spec.palette as unknown as Record<string, string>;
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <Input value={layer.name} onChange={(e) => onLayer({ name: e.target.value })} className="h-8 font-medium" />
        <div className="flex shrink-0 gap-0.5">
          <Button size="icon-sm" variant="ghost" onClick={() => onMove(1)} title="Bring forward">
            <ArrowUp />
          </Button>
          <Button size="icon-sm" variant="ghost" onClick={() => onMove(-1)} title="Send backward">
            <ArrowDown />
          </Button>
          <Button size="icon-sm" variant="ghost" onClick={() => onLayer({ hidden: !layer.hidden })} title={layer.hidden ? "Show" : "Hide"}>
            {layer.hidden ? <EyeOff /> : <Eye />}
          </Button>
          <Button size="icon-sm" variant="ghost" onClick={onDelete} title="Delete layer">
            <Trash2 />
          </Button>
        </div>
      </div>

      {layer.type === "text" && <TextFields l={layer} onLayer={onLayer} tokens={tokens} />}
      {layer.type === "photo" && <PhotoFields l={layer} onLayer={onLayer} tokens={tokens} photos={photos} />}
      {layer.type === "logo" && <LogoFields l={layer} onLayer={onLayer} tokens={tokens} logos={logos} />}
      {layer.type === "shape" && <ShapeFields l={layer} onLayer={onLayer} tokens={tokens} />}

      <Separator />
      <div className="grid grid-cols-4 gap-2">
        {(["x", "y", "w", "h"] as const).map((k) => (
          <Field key={k} label={k.toUpperCase()}>
            <Input
              type="number"
              step={0.5}
              value={Math.round(layer[k] * 1000) / 10}
              onChange={(e) => onLayer({ [k]: Number(e.target.value) / 100 } as Partial<Layer>)}
              className="h-8 px-2 font-mono text-xs"
            />
          </Field>
        ))}
      </div>
      <Field label="Rotation">
        <NumberSlider value={layer.rotation} min={-45} max={45} step={0.5} onChange={(v) => onLayer({ rotation: v })} format={(v) => `${v}°`} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Opacity">
          <NumberSlider value={layer.opacity} min={0} max={1} onChange={(v) => onLayer({ opacity: v })} format={pct} />
        </Field>
        <Field label="Blend">
          <Choice value={layer.blend} onChange={(v) => onLayer({ blend: v })} options={["normal", "multiply", "screen"].map((v) => ({ value: v as Layer["blend"], label: cap(v) }))} />
        </Field>
      </div>
    </div>
  );
}

function TextFields({ l, onLayer, tokens }: { l: TextLayer; onLayer: (p: Partial<TextLayer>) => void; tokens: Record<string, string> }) {
  const weights = FONTS[l.font as FontId]?.weights ?? [400];
  return (
    <div className="space-y-4">
      <Field label="Text" hint="Typeset exactly as written. Line breaks are kept.">
        <Textarea value={l.text} rows={Math.min(5, Math.max(2, l.text.split("\n").length))} onChange={(e) => onLayer({ text: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Font">
          <Choice value={l.font} onChange={(v) => onLayer({ font: v, weight: FONTS[v as FontId].weights.includes(l.weight as never) ? l.weight : FONTS[v as FontId].weights[FONTS[v as FontId].weights.length - 1] })} options={FONT_IDS.map((f) => ({ value: f, label: <span style={{ fontFamily: `"${f}"` }}>{f}</span> }))} />
        </Field>
        <Field label="Weight">
          <Choice value={String(weights.includes(l.weight as never) ? l.weight : weights[0])} onChange={(v) => onLayer({ weight: Number(v) })} options={weights.map((w) => ({ value: String(w), label: String(w) }))} />
        </Field>
      </div>
      <label className="flex items-center justify-between gap-2 text-sm">
        <span>
          Fill box width
          <span className="block text-xs text-muted-foreground">Scales type so each line spans the box, like wood type.</span>
        </span>
        <Switch checked={l.fill} onCheckedChange={(v) => onLayer({ fill: v })} />
      </label>
      {!l.fill && (
        <Field label="Size (max)">
          <NumberSlider value={l.size} min={0.01} max={0.4} step={0.002} onChange={(v) => onLayer({ size: v })} format={(v) => `${(v * 100).toFixed(1)}`} />
        </Field>
      )}
      <Field label="Colour">
        <ColorField value={l.color} onChange={(v) => onLayer({ color: v })} tokens={tokens} />
      </Field>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Align">
          <Choice value={l.align} onChange={(v) => onLayer({ align: v })} options={["left", "center", "right"].map((v) => ({ value: v as TextLayer["align"], label: cap(v) }))} />
        </Field>
        <Field label="Vertical">
          <Choice value={l.valign} onChange={(v) => onLayer({ valign: v })} options={["top", "middle", "bottom"].map((v) => ({ value: v as TextLayer["valign"], label: cap(v) }))} />
        </Field>
        <Field label="Case">
          <Choice value={l.transform} onChange={(v) => onLayer({ transform: v })} options={[{ value: "none" as const, label: "As typed" }, { value: "upper" as const, label: "UPPER" }, { value: "lower" as const, label: "lower" }]} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Tracking">
          <NumberSlider value={l.tracking} min={-0.08} max={0.4} step={0.005} onChange={(v) => onLayer({ tracking: v })} />
        </Field>
        <Field label="Leading">
          <NumberSlider value={l.leading} min={0.75} max={1.8} step={0.01} onChange={(v) => onLayer({ leading: v })} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Role" hint="Used by checks">
          <Choice value={l.role} onChange={(v) => onLayer({ role: v })} options={TEXT_ROLES.map((r) => ({ value: r, label: cap(r) }))} />
        </Field>
        <Misregister value={l.misregister} onChange={(v) => onLayer({ misregister: v })} tokens={tokens} />
      </div>
    </div>
  );
}

function Misregister({ value, onChange, tokens }: { value: TextLayer["misregister"]; onChange: (v: TextLayer["misregister"]) => void; tokens: Record<string, string> }) {
  return (
    <Field label="Misregistration">
      <div className="space-y-2">
        <Switch checked={!!value} onCheckedChange={(v) => onChange(v ? { dx: 0.004, dy: 0.003, color: "$accent" } : null)} />
        {value && <ColorField value={value.color} onChange={(c) => onChange({ ...value, color: c })} tokens={tokens} />}
      </div>
    </Field>
  );
}

function AssetStrip({ assets, value, onPick, contain }: { assets: Asset[]; value: string | null; onPick: (a: Asset) => void; contain?: boolean }) {
  if (!assets.length) return <p className="text-xs text-muted-foreground">Nothing uploaded yet. Add some in the Band kit.</p>;
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-1">
      {assets.map((a) => (
        <button
          key={a.id}
          onClick={() => onPick(a)}
          title={a.name}
          className={cn("relative size-14 shrink-0 overflow-hidden rounded-md border", value === a.id ? "border-primary ring-2 ring-primary/50" : "border-border hover:border-foreground/40", contain && "checker")}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/api/assets/${a.id}/preview`} alt={a.name} className={cn("h-full w-full", contain ? "object-contain p-1" : "object-cover")} />
        </button>
      ))}
    </div>
  );
}

function PhotoFields({ l, onLayer, tokens, photos }: { l: PhotoLayer; onLayer: (p: Partial<PhotoLayer>) => void; tokens: Record<string, string>; photos: Asset[] }) {
  const t = l.treatment;
  const setT = (p: Partial<PhotoLayer["treatment"]>) => onLayer({ treatment: { ...t, ...p } });
  return (
    <div className="space-y-4">
      <Field label="Photo">
        <AssetStrip assets={photos} value={l.assetId} onPick={(a) => onLayer({ assetId: a.id, focusX: a.focalX, focusY: a.focalY })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Fit">
          <Choice value={l.fit} onChange={(v) => onLayer({ fit: v })} options={[{ value: "cover" as const, label: "Fill frame (crop)" }, { value: "contain" as const, label: "Whole photo" }]} />
        </Field>
        <Field label="Frame">
          <Choice value={l.mask} onChange={(v) => onLayer({ mask: v })} options={["rect", "ellipse", "arch", "slant"].map((v) => ({ value: v as PhotoLayer["mask"], label: cap(v === "rect" ? "rectangle" : v === "ellipse" ? "circle / oval" : v) }))} />
        </Field>
      </div>
      <Field label="Zoom" hint="One uniform scale factor; the photo is never stretched.">
        <NumberSlider value={l.zoom} min={1} max={3} onChange={(v) => onLayer({ zoom: v })} format={(v) => `${v.toFixed(2)}×`} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Focus X">
          <NumberSlider value={l.focusX} min={0} max={1} onChange={(v) => onLayer({ focusX: v })} format={pct} />
        </Field>
        <Field label="Focus Y">
          <NumberSlider value={l.focusY} min={0} max={1} onChange={(v) => onLayer({ focusY: v })} format={pct} />
        </Field>
      </div>
      <Separator />
      <Field label="Colour treatment" hint="Maps colours pixel-by-pixel. Shapes and edges stay identical to the original.">
        <Choice
          value={t.mode}
          onChange={(v) => setT({ mode: v })}
          options={[
            { value: "original" as const, label: "Original colour" },
            { value: "mono" as const, label: "Black & white" },
            { value: "duotone" as const, label: "Duotone" },
            { value: "tint" as const, label: "Tint" },
            { value: "threshold" as const, label: "Photocopy (1-bit)" },
          ]}
        />
      </Field>
      {(t.mode === "duotone" || t.mode === "tint" || t.mode === "threshold") && (
        <div className="grid gap-3">
          <Field label="Shadows">
            <ColorField value={t.dark} onChange={(v) => setT({ dark: v })} tokens={tokens} />
          </Field>
          <Field label="Highlights">
            <ColorField value={t.light} onChange={(v) => setT({ light: v })} tokens={{ ...tokens, white: "#FFFFFF" }} />
          </Field>
        </div>
      )}
      {t.mode === "threshold" && (
        <Field label="Threshold">
          <NumberSlider value={t.threshold} min={0.1} max={0.9} onChange={(v) => setT({ threshold: v })} format={pct} />
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Contrast">
          <NumberSlider value={t.contrast} min={-1} max={1} onChange={(v) => setT({ contrast: v })} />
        </Field>
        <Field label="Brightness">
          <NumberSlider value={t.brightness} min={-1} max={1} onChange={(v) => setT({ brightness: v })} />
        </Field>
      </div>
      <Misregister value={l.misregister} onChange={(v) => onLayer({ misregister: v })} tokens={tokens} />
    </div>
  );
}

function LogoFields({ l, onLayer, tokens, logos }: { l: LogoLayer; onLayer: (p: Partial<LogoLayer>) => void; tokens: Record<string, string>; logos: Asset[] }) {
  return (
    <div className="space-y-4">
      <Field label="Logo">
        <AssetStrip assets={logos} value={l.assetId} onPick={(a) => onLayer({ assetId: a.id })} contain />
      </Field>
      <Field label="Align in box">
        <Choice value={l.align} onChange={(v) => onLayer({ align: v })} options={["left", "center", "right"].map((v) => ({ value: v as LogoLayer["align"], label: cap(v) }))} />
      </Field>
      <label className="flex items-center justify-between text-sm">
        <span>
          Recolour
          <span className="block text-xs text-muted-foreground">Off = the logo&apos;s original colours.</span>
        </span>
        <Switch checked={!!l.recolor} onCheckedChange={(v) => onLayer({ recolor: v ? "$ink" : null })} />
      </label>
      {l.recolor && (
        <>
          <ColorField value={l.recolor} onChange={(v) => onLayer({ recolor: v })} tokens={tokens} />
          <Field label="Mode" hint="Tone keeps interior detail; Solid flattens every opaque pixel to one ink.">
            <Choice value={l.recolorMode} onChange={(v) => onLayer({ recolorMode: v })} options={[{ value: "tone" as const, label: "Tone (keeps detail)" }, { value: "solid" as const, label: "Solid single ink" }]} />
          </Field>
        </>
      )}
    </div>
  );
}

function ShapeFields({ l, onLayer, tokens }: { l: ShapeLayer; onLayer: (p: Partial<ShapeLayer>) => void; tokens: Record<string, string> }) {
  return (
    <div className="space-y-4">
      <Field label="Shape">
        <Choice value={l.shape} onChange={(v) => onLayer({ shape: v })} options={["rect", "ellipse", "ring", "stripes", "sunburst"].map((v) => ({ value: v as ShapeLayer["shape"], label: cap(v === "rect" ? "rectangle" : v) }))} />
      </Field>
      <Field label="Ink">
        <ColorField value={l.fill} onChange={(v) => onLayer({ fill: v })} tokens={tokens} />
      </Field>
      {(l.shape === "sunburst" || l.shape === "stripes") && (
        <Field label={l.shape === "sunburst" ? "Rays" : "Stripes"}>
          <NumberSlider value={l.rays} min={4} max={48} step={1} onChange={(v) => onLayer({ rays: v })} format={(v) => String(v)} />
        </Field>
      )}
    </div>
  );
}

function BackgroundInspector({ spec, onSpec }: { spec: FlyerSpec; onSpec: (s: FlyerSpec) => void }) {
  const tokens = spec.palette as unknown as Record<string, string>;
  const setTex = (i: number, p: Partial<Texture>) => onSpec({ ...spec, background: { ...spec.background, textures: spec.background.textures.map((t, j) => (i === j ? { ...t, ...p } : t)) } });
  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-medium">Flyer</h3>
        <p className="text-xs text-muted-foreground">Select a layer on the canvas or in the list to edit it. These settings apply to the whole flyer.</p>
      </div>
      <Field label="Palette (inks)" hint="Layers that use palette inks update together.">
        <div className="grid grid-cols-2 gap-2">
          {(["paper", "ink", "accent", "accent2"] as const).map((k) => (
            <label key={k} className="flex items-center gap-2 text-xs">
              <span className="relative size-7 shrink-0 overflow-hidden rounded-sm border border-border">
                <input type="color" value={spec.palette[k]} onChange={(e) => onSpec({ ...spec, palette: { ...spec.palette, [k]: e.target.value } })} className="absolute -inset-2 size-12 cursor-pointer" />
              </span>
              <span className="capitalize">{k === "accent2" ? "Accent 2" : k}</span>
            </label>
          ))}
        </div>
      </Field>
      <Field label="Background">
        <ColorField value={spec.background.color} onChange={(v) => onSpec({ ...spec, background: { ...spec.background, color: v } })} tokens={tokens} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Display face">
          <Choice value={spec.fonts.display} onChange={(v) => onSpec(setFonts(spec, { ...spec.fonts, display: v }))} options={FONT_IDS.map((f) => ({ value: f, label: f }))} />
        </Field>
        <Field label="Text face">
          <Choice value={spec.fonts.text} onChange={(v) => onSpec(setFonts(spec, { ...spec.fonts, text: v }))} options={FONT_IDS.map((f) => ({ value: f, label: f }))} />
        </Field>
      </div>
      <Separator />
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium">Print texture</h4>
          <Button size="xs" variant="outline" onClick={() => onSpec({ ...spec, background: { ...spec.background, textures: [...spec.background.textures, { kind: "grain", color: "$ink", opacity: 0.12, scale: 1 }] } })}>
            Add
          </Button>
        </div>
        {spec.background.textures.length === 0 && <p className="text-xs text-muted-foreground">Clean, no texture.</p>}
        {spec.background.textures.map((t, i) => (
          <div key={i} className="space-y-2 rounded-md border border-border/60 p-2.5">
            <div className="flex items-center gap-2">
              <Choice value={t.kind} onChange={(v) => setTex(i, { kind: v })} options={["grain", "speckle", "paper", "halftone", "lines"].map((k) => ({ value: k as Texture["kind"], label: cap(k) }))} className="h-7" />
              <Button size="icon-xs" variant="ghost" onClick={() => onSpec({ ...spec, background: { ...spec.background, textures: spec.background.textures.filter((_, j) => j !== i) } })}>
                <Trash2 />
              </Button>
            </div>
            <NumberSlider value={t.opacity} min={0} max={0.7} onChange={(v) => setTex(i, { opacity: v })} format={pct} />
            <NumberSlider value={t.scale} min={0.3} max={4} onChange={(v) => setTex(i, { scale: v })} format={(v) => `${v.toFixed(1)}×`} />
            <ColorField value={t.color} onChange={(v) => setTex(i, { color: v })} tokens={tokens} />
          </div>
        ))}
      </div>
    </div>
  );
}
