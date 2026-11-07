"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

export function Field({ label, hint, children, className }: { label: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-1.5", className)}>
      <Label className="text-xs font-medium text-muted-foreground">{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Choice<T extends string>({
  value,
  onChange,
  options,
  className,
  placeholder,
}: {
  value: T | null;
  onChange: (v: T) => void;
  options: { value: T; label: React.ReactNode }[];
  className?: string;
  placeholder?: string;
}) {
  return (
    <Select
      value={value}
      items={options}
      onValueChange={(v) => {
        if (v !== null) onChange(v as T);
      }}
    >
      <SelectTrigger className={cn("w-full", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function NumberSlider({
  value,
  onChange,
  min,
  max,
  step = 0.01,
  format,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  format?: (v: number) => string;
}) {
  return (
    <div className="flex items-center gap-3">
      <Slider
        value={value}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(Array.isArray(v) ? v[0] : (v as number))}
        className="flex-1"
      />
      <span className="w-12 text-right font-mono text-xs tabular-nums text-muted-foreground">{format ? format(value) : value.toFixed(2)}</span>
    </div>
  );
}

const HEX = /^#[0-9a-fA-F]{6}$/;

export function ColorField({ value, onChange, tokens }: { value: string; onChange: (v: string) => void; tokens?: Record<string, string> }) {
  const resolved = value.startsWith("$") && tokens ? tokens[value.slice(1)] ?? "#000000" : value;
  const [draft, setDraft] = useState(value);
  const [prev, setPrev] = useState(value);
  if (prev !== value) {
    setPrev(value);
    setDraft(value);
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tokens &&
        Object.entries(tokens).map(([k, hex]) => (
          <button
            key={k}
            type="button"
            title={`Palette: ${k}`}
            onClick={() => onChange(`$${k}`)}
            className={cn("size-6 rounded-sm border border-border", value === `$${k}` && "ring-2 ring-ring ring-offset-1 ring-offset-background")}
            style={{ background: hex }}
          />
        ))}
      <label className="relative size-6 cursor-pointer overflow-hidden rounded-sm border border-border" title="Custom colour">
        <input type="color" value={HEX.test(resolved) ? resolved : "#000000"} onChange={(e) => onChange(e.target.value)} className="absolute -inset-2 size-10 cursor-pointer" />
      </label>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => (HEX.test(draft) || draft.startsWith("$") ? onChange(draft) : setDraft(value))}
        className="h-6 w-20 rounded-sm border border-input bg-transparent px-1.5 font-mono text-xs"
      />
    </div>
  );
}
