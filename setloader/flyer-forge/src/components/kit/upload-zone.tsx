"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { ACCEPTED_TYPES, uploadAsset } from "@/lib/assets-client";
import type { Asset } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Pending {
  name: string;
  progress: number;
}

export function UploadZone({
  kind,
  extraMeta,
  onUploaded,
  label,
  hint,
  className,
}: {
  kind: Asset["kind"];
  extraMeta?: () => { photoKind?: string; memberIds?: string[] };
  onUploaded: (a: Asset) => void;
  label: string;
  hint: string;
  className?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);

  const handle = async (files: FileList | File[]) => {
    const list = [...files].filter((f) => {
      if (!ACCEPTED_TYPES.includes(f.type)) {
        toast.error(`${f.name}: use PNG, JPEG, WebP or SVG`);
        return false;
      }
      if (f.size > 60 * 1024 * 1024) {
        toast.error(`${f.name}: larger than 60 MB`);
        return false;
      }
      return true;
    });
    for (const file of list) {
      const name = file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
      setPending((p) => [...p, { name, progress: 0 }]);
      try {
        const asset = await uploadAsset(file, { kind, name, ...(extraMeta?.() ?? {}) }, (progress) =>
          setPending((p) => p.map((x) => (x.name === name ? { ...x, progress } : x))),
        );
        onUploaded(asset);
      } catch (e) {
        toast.error(`${file.name}: ${e instanceof Error ? e.message : "upload failed"}`);
      } finally {
        setPending((p) => p.filter((x) => x.name !== name));
      }
    }
  };

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          void handle(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border px-4 py-6 text-center transition-colors hover:border-foreground/40 hover:bg-muted/30",
          over && "border-foreground/60 bg-muted/40",
        )}
      >
        <Upload className="size-5 text-muted-foreground" />
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPTED_TYPES.join(",")}
        className="hidden"
        onChange={(e) => {
          if (e.target.files) void handle(e.target.files);
          e.target.value = "";
        }}
      />
      {pending.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {pending.map((p) => (
            <li key={p.name} className="text-xs text-muted-foreground">
              <div className="flex justify-between">
                <span className="truncate">{p.name}</span>
                <span>{Math.round(p.progress * 100)}%</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded bg-muted">
                <div className="h-full bg-primary transition-all" style={{ width: `${Math.max(5, p.progress * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
