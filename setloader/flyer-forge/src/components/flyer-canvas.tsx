"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { FORMATS, type FlyerSpec } from "@/lib/spec";
import { fontsFor } from "@/lib/render/checks";
import { renderFlyer, type RenderReport, type SourceImage } from "@/lib/render/render";

interface Props {
  spec: FlyerSpec;
  images: Map<string, SourceImage>;
  wireframe?: boolean;
  className?: string;
  /** Rendering resolution in CSS pixels; the canvas scales to fill its container. */
  resolution?: number;
  onReport?: (r: RenderReport) => void;
  children?: React.ReactNode;
}

export function FlyerCanvas({ spec, images, wireframe, className, resolution = 600, onReport, children }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);
  const f = FORMATS[spec.format];
  const onReportRef = useRef(onReport);
  useEffect(() => {
    onReportRef.current = onReport;
  });

  useEffect(() => {
    let cancelled = false;
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = Math.min(2, typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);
    const width = Math.round(resolution * dpr);
    void fontsFor(spec).then(() => {
      if (cancelled) return;
      canvas.width = width;
      canvas.height = Math.round((width * f.h) / f.w);
      const report = renderFlyer(canvas.getContext("2d")!, spec, images, { width, wireframe });
      setReady(true);
      onReportRef.current?.(report);
    });
    return () => {
      cancelled = true;
    };
  }, [spec, images, wireframe, resolution, f.h, f.w]);

  return (
    <div className={cn("relative w-full overflow-hidden bg-muted shadow-sm", className)} style={{ aspectRatio: `${f.w} / ${f.h}` }}>
      <canvas ref={ref} className={cn("absolute inset-0 h-full w-full transition-opacity", ready ? "opacity-100" : "opacity-0")} />
      {!ready && <div className="absolute inset-0 animate-pulse bg-muted" />}
      {children}
    </div>
  );
}
