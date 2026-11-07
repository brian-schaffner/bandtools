"use client";

import { Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Choice, Field } from "@/components/fields";
import { FORMAT_IDS, FORMATS, type Brief } from "@/lib/spec";
import type { Asset } from "@/lib/types";
import { cn } from "@/lib/utils";
import { withBase } from "@/lib/base-path";

const MOODS = ["Gritty garage", "Late-night jazz club", "Warm Americana", "Loud & fast punk", "Dreamy indie", "Psychedelic", "Clean & modern"];

export function BriefForm({
  brief,
  onChange,
  photos,
  logos,
  showAssets = true,
}: {
  brief: Brief;
  onChange: (b: Brief) => void;
  photos: Asset[];
  logos: Asset[];
  showAssets?: boolean;
}) {
  const set = <K extends keyof Brief>(k: K, v: Brief[K]) => onChange({ ...brief, [k]: v });
  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2">
        <Field label="Date">
          <Input type="date" value={brief.date} onChange={(e) => set("date", e.target.value)} />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Doors">
            <Input value={brief.doors} onChange={(e) => set("doors", e.target.value)} placeholder="8pm" />
          </Field>
          <Field label="Show">
            <Input value={brief.showTime} onChange={(e) => set("showTime", e.target.value)} placeholder="9pm" />
          </Field>
          <Field label="Ends">
            <Input value={brief.endTime} onChange={(e) => set("endTime", e.target.value)} placeholder="12am" />
          </Field>
        </div>
        <Field label="Venue">
          <Input value={brief.venue} onChange={(e) => set("venue", e.target.value)} placeholder="The Camel" />
        </Field>
        <Field label="City">
          <Input value={brief.city} onChange={(e) => set("city", e.target.value)} placeholder="Richmond, VA" />
        </Field>
        <Field label="Address" className="sm:col-span-2">
          <Input value={brief.address} onChange={(e) => set("address", e.target.value)} placeholder="1621 W Broad St, Richmond, VA" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Price">
            <Input value={brief.price} onChange={(e) => set("price", e.target.value)} placeholder="$12 adv / $15 door" />
          </Field>
          <Field label="Ages">
            <Input value={brief.ages} onChange={(e) => set("ages", e.target.value)} placeholder="21+" />
          </Field>
        </div>
        <Field label="Support acts" hint="Comma-separated">
          <Input value={brief.support.join(", ")} onChange={(e) => set("support", e.target.value.split(",").map((s) => s.trimStart()))} placeholder="Low Tide, The Wrens" />
        </Field>
        <Field label="Tickets / link">
          <Input value={brief.tickets} onChange={(e) => set("tickets", e.target.value)} placeholder="tix.thecamel.org" />
        </Field>
        <Field label="Headline or tour name (optional)">
          <Input value={brief.headline} onChange={(e) => set("headline", e.target.value)} placeholder="Record release show" />
        </Field>
      </section>

      <section className="grid gap-4 sm:grid-cols-[1fr_220px]">
        <Field label="Mood / direction" hint="Plain words work best. This steers which print traditions get proposed.">
          <Textarea value={brief.mood} rows={2} onChange={(e) => set("mood", e.target.value)} placeholder="Sweaty basement show, a bit 70s, no neon" />
          <div className="flex flex-wrap gap-1.5 pt-1">
            {MOODS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => set("mood", brief.mood ? `${brief.mood}, ${m.toLowerCase()}` : m)}
                className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground hover:text-foreground"
              >
                + {m}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Format">
          <Choice value={brief.format} onChange={(v) => set("format", v)} options={FORMAT_IDS.map((f) => ({ value: f, label: FORMATS[f].label }))} />
        </Field>
      </section>

      {showAssets && (
        <section className="space-y-4">
          <Field label="Feature photo">
            {photos.length === 0 ? (
              <p className="text-sm text-muted-foreground">No photos uploaded yet. Concepts will leave a photo frame you can fill later.</p>
            ) : (
              <div className="flex gap-2 overflow-x-auto pb-1">
                <PickTile active={!brief.photoId} onClick={() => set("photoId", null)} label="Auto" />
                {photos.map((p) => (
                  <PickTile key={p.id} active={brief.photoId === p.id} onClick={() => set("photoId", p.id)} src={withBase(`/api/assets/${p.id}/preview`)} label={p.name} />
                ))}
              </div>
            )}
          </Field>
          <Field label="Logo">
            <div className="flex gap-2 overflow-x-auto pb-1">
              <PickTile active={!brief.logoId} onClick={() => set("logoId", null)} label="Auto" />
              <PickTile active={brief.logoId === "none"} onClick={() => set("logoId", "none")} label="Typeset name" />
              {logos.map((l) => (
                <PickTile key={l.id} active={brief.logoId === l.id} onClick={() => set("logoId", l.id)} src={withBase(`/api/assets/${l.id}/preview`)} label={l.name} contain />
              ))}
            </div>
          </Field>
        </section>
      )}
    </div>
  );
}

function PickTile({ active, onClick, src, label, contain }: { active: boolean; onClick: () => void; src?: string; label: string; contain?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "relative grid size-20 shrink-0 place-items-center overflow-hidden rounded-md border text-xs text-muted-foreground transition-colors",
        active ? "border-primary ring-2 ring-primary/50" : "border-border hover:border-foreground/40",
        contain && "checker",
      )}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={label} className={cn("absolute inset-0 h-full w-full", contain ? "object-contain p-2" : "object-cover")} />
      ) : (
        <span className="px-1 text-center">{label}</span>
      )}
      {active && (
        <span className="absolute right-1 top-1 rounded-full bg-primary p-0.5 text-primary-foreground">
          <Check className="size-3" />
        </span>
      )}
    </button>
  );
}
