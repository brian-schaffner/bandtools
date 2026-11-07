"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Download, ShieldCheck, Star, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Choice, Field } from "@/components/fields";
import { api } from "@/lib/api";
import { loadAsset } from "@/lib/assets-client";
import type { Asset, Member, PhotoKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import { withBase } from "@/lib/base-path";

export function formatBytes(n: number) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}

export const PHOTO_KINDS: { value: PhotoKind; label: string }[] = [
  { value: "group", label: "Group" },
  { value: "individual", label: "Individual" },
  { value: "live", label: "Live" },
  { value: "other", label: "Other" },
];

export function AssetDialog({
  asset,
  members,
  open,
  onOpenChange,
  onChanged,
  onDeleted,
}: {
  asset: Asset | null;
  members: Member[];
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onChanged: (a: Asset) => void;
  onDeleted: (id: string) => void;
}) {
  const [draft, setDraft] = useState<Asset | null>(asset);
  const [saving, setSaving] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [prevAsset, setPrevAsset] = useState(asset);
  if (prevAsset !== asset) {
    setPrevAsset(asset);
    setDraft(asset);
  }
  if (!draft || !asset) return null;

  const patch = async (body: Partial<Asset>) => {
    setSaving(true);
    try {
      const updated = await api<Asset>(`/api/assets/${asset.id}`, { method: "PATCH", json: body });
      onChanged(updated);
      setDraft(updated);
      return updated;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  const save = async () => {
    const ok = await patch({
      name: draft.name,
      photoKind: draft.photoKind ?? undefined,
      memberIds: draft.memberIds,
      credit: draft.credit,
      notes: draft.notes,
      focalX: draft.focalX,
      focalY: draft.focalY,
    } as Partial<Asset>);
    if (ok) {
      toast.success("Saved");
      onOpenChange(false);
    }
  };

  const downloadOriginal = async () => {
    try {
      const { image, verified } = await loadAsset(asset);
      const a = document.createElement("a");
      a.href = image.src;
      if (asset.mime !== "image/svg+xml") {
        a.download = asset.name || asset.id;
        a.click();
      } else {
        const parts = await Promise.all(Array.from({ length: asset.chunkCount }, (_, i) => fetch(withBase(`/api/assets/${asset.id}/chunks/${i}`)).then((r) => r.arrayBuffer())));
        const url = URL.createObjectURL(new Blob(parts, { type: asset.mime }));
        a.href = url;
        a.download = `${asset.name || asset.id}.svg`;
        a.click();
      }
      toast.success(verified ? "Original downloaded; fingerprint verified" : "Downloaded, but the fingerprint did not match");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed");
    }
  };

  const remove = async () => {
    try {
      await api(`/api/assets/${asset.id}`, { method: "DELETE" });
      onDeleted(asset.id);
      setConfirm(false);
      onOpenChange(false);
      toast.success("Deleted");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const isPhoto = asset.kind === "photo";

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{isPhoto ? "Photo details" : "Logo details"}</DialogTitle>
            <DialogDescription>
              Only the details below are editable. The original file is stored exactly as uploaded and is never modified.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-6 md:grid-cols-[1.2fr_1fr]">
            <div className="space-y-2">
              <FocalPicker asset={asset} focal={{ x: draft.focalX, y: draft.focalY }} onChange={isPhoto ? (f) => setDraft({ ...draft, focalX: f.x, focalY: f.y }) : undefined} />
              {isPhoto && <p className="text-xs text-muted-foreground">Click the photo to set the focal point. Crops in every flyer centre on it.</p>}
              <div className="rounded-md border border-border/60 bg-muted/30 p-3 text-xs text-muted-foreground">
                <div className="mb-1 flex items-center gap-1.5 font-medium text-foreground">
                  <ShieldCheck className="size-3.5 text-emerald-400" /> Original locked
                </div>
                <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono">
                  <span>size</span>
                  <span>
                    {asset.width}×{asset.height} px · {formatBytes(asset.byteSize)}
                  </span>
                  <span>type</span>
                  <span>{asset.mime}</span>
                  <span>sha256</span>
                  <span className="truncate" title={asset.sha256}>
                    {asset.sha256}
                  </span>
                </div>
              </div>
            </div>
            <div className="space-y-4">
              <Field label="Name">
                <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={isPhoto ? "e.g. Rooftop group shot" : "e.g. Primary wordmark, white"} />
              </Field>
              {isPhoto && (
                <Field label="Type">
                  <Choice value={draft.photoKind ?? "group"} onChange={(v) => setDraft({ ...draft, photoKind: v })} options={PHOTO_KINDS} />
                </Field>
              )}
              {isPhoto && (
                <Field label="Who's in it">
                  {members.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {members.map((m) => {
                        const on = draft.memberIds.includes(m.id);
                        return (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => setDraft({ ...draft, memberIds: on ? draft.memberIds.filter((x) => x !== m.id) : [...draft.memberIds, m.id] })}
                            className={cn("rounded-full border px-2.5 py-1 text-xs transition-colors", on ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:text-foreground")}
                          >
                            {m.name}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">Add band members on the Band kit page to tag photos.</p>
                  )}
                </Field>
              )}
              {isPhoto && (
                <Field label="Photo credit">
                  <Input value={draft.credit} onChange={(e) => setDraft({ ...draft, credit: e.target.value })} placeholder="Photographer" />
                </Field>
              )}
              <Field label="Notes">
                <Textarea value={draft.notes} rows={3} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} placeholder={isPhoto ? "Usage notes, rights, where it was shot" : "When to use this version (dark backgrounds, small sizes…)"} />
              </Field>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => patch({ isPrimary: !asset.isPrimary })} disabled={saving}>
                  <Star className={cn("size-3.5", asset.isPrimary && "fill-current text-amber-400")} />
                  {asset.isPrimary ? "Primary" : "Make primary"}
                </Button>
                <Button variant="outline" size="sm" onClick={downloadOriginal}>
                  <Download className="size-3.5" /> Original
                </Button>
                <Button variant="outline" size="sm" onClick={() => patch({ archived: !asset.archived })} disabled={saving}>
                  {asset.archived ? "Restore" : "Archive"}
                </Button>
                <Button variant="destructive" size="sm" onClick={() => setConfirm(true)}>
                  <Trash2 className="size-3.5" /> Delete
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={save} disabled={saving}>
              Save details
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this {isPhoto ? "photo" : "logo"}?</AlertDialogTitle>
            <AlertDialogDescription>
              The original is removed permanently. Flyers that use it will show an empty frame until you pick another. Archive it instead to keep old flyers intact.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={remove}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function FocalPicker({ asset, focal, onChange }: { asset: Asset; focal: { x: number; y: number }; onChange?: (f: { x: number; y: number }) => void }) {
  return (
    <div
      className={cn("checker relative w-full overflow-hidden rounded-md border border-border", onChange && "cursor-crosshair")}
      style={{ aspectRatio: `${asset.width} / ${asset.height}` }}
      onClick={(e) => {
        if (!onChange) return;
        const r = e.currentTarget.getBoundingClientRect();
        onChange({ x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={withBase(`/api/assets/${asset.id}/preview`)} alt={asset.name} className="absolute inset-0 h-full w-full object-contain" />
      {onChange && (
        <div
          className="pointer-events-none absolute size-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-[0_0_0_2px_rgba(0,0,0,0.6)]"
          style={{ left: `${focal.x * 100}%`, top: `${focal.y * 100}%` }}
        />
      )}
    </div>
  );
}
