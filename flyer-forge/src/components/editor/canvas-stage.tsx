"use client";

import { useRef } from "react";
import { FlyerCanvas } from "@/components/flyer-canvas";
import type { FlyerSpec, Layer } from "@/lib/spec";
import type { RenderReport, SourceImage } from "@/lib/render/render";

type Drag = { mode: "move" | "resize"; id: string; startX: number; startY: number; orig: Pick<Layer, "x" | "y" | "w" | "h"> };

export function CanvasStage({
  spec,
  images,
  selectedId,
  onSelect,
  onLayerChange,
  onCommit,
  onReport,
  wireframe,
}: {
  spec: FlyerSpec;
  images: Map<string, SourceImage>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Live update while dragging (not added to undo history). */
  onLayerChange: (id: string, patch: Partial<Layer>) => void;
  /** Called once a drag ends so the change becomes one undo step. */
  onCommit: () => void;
  onReport?: (r: RenderReport) => void;
  wireframe?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag | null>(null);
  const selected = spec.layers.find((l) => l.id === selectedId) ?? null;

  const rel = (e: React.PointerEvent) => {
    const r = box.current!.getBoundingClientRect();
    return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
  };

  const hit = (x: number, y: number) => {
    for (let i = spec.layers.length - 1; i >= 0; i--) {
      const l = spec.layers[i];
      if (l.hidden) continue;
      // Ignore layers that cover most of the canvas (backgrounds, sunbursts) unless nothing else is under the pointer.
      if (l.w * l.h > 0.9) continue;
      if (x >= l.x && x <= l.x + l.w && y >= l.y && y <= l.y + l.h) return l.id;
    }
    return null;
  };

  return (
    <div
      ref={box}
      className="relative touch-none select-none"
      onPointerDown={(e) => {
        if ((e.target as HTMLElement).dataset.handle) return;
        const p = rel(e);
        const id = hit(p.x, p.y);
        onSelect(id);
        if (id) {
          const l = spec.layers.find((x) => x.id === id)!;
          drag.current = { mode: "move", id, startX: p.x, startY: p.y, orig: { x: l.x, y: l.y, w: l.w, h: l.h } };
          (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        }
      }}
      onPointerMove={(e) => {
        const d = drag.current;
        if (!d) return;
        const p = rel(e);
        const dx = p.x - d.startX;
        const dy = p.y - d.startY;
        if (d.mode === "move") onLayerChange(d.id, { x: d.orig.x + dx, y: d.orig.y + dy });
        else onLayerChange(d.id, { w: Math.max(0.02, d.orig.w + dx), h: Math.max(0.01, d.orig.h + dy) });
      }}
      onPointerUp={() => {
        if (drag.current) {
          drag.current = null;
          onCommit();
        }
      }}
    >
      <FlyerCanvas spec={spec} images={images} resolution={720} onReport={onReport} wireframe={wireframe} className="rounded-sm">
        {selected && (
          <div
            className="pointer-events-none absolute border border-sky-400 shadow-[0_0_0_1px_rgba(0,0,0,0.4)]"
            style={{
              left: `${selected.x * 100}%`,
              top: `${selected.y * 100}%`,
              width: `${selected.w * 100}%`,
              height: `${selected.h * 100}%`,
              transform: selected.rotation ? `rotate(${selected.rotation}deg)` : undefined,
            }}
          >
            <span className="absolute -top-5 left-0 rounded-sm bg-sky-500 px-1 text-[10px] font-medium text-white">{selected.name || selected.type}</span>
            <div
              data-handle="resize"
              className="pointer-events-auto absolute -bottom-1.5 -right-1.5 size-3 cursor-nwse-resize rounded-sm border border-white bg-sky-500"
              onPointerDown={(e) => {
                e.stopPropagation();
                const p = rel(e);
                drag.current = { mode: "resize", id: selected.id, startX: p.x, startY: p.y, orig: { x: selected.x, y: selected.y, w: selected.w, h: selected.h } };
                box.current?.setPointerCapture(e.pointerId);
              }}
            />
          </div>
        )}
      </FlyerCanvas>
    </div>
  );
}
