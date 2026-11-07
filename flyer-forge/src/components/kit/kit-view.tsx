"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Star, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Choice, Field } from "@/components/fields";
import { AssetDialog, formatBytes, PHOTO_KINDS } from "./asset-dialog";
import { UploadZone } from "./upload-zone";
import { useAssets, useBand } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import type { Asset, Band, Member, PhotoKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import { withBase } from "@/lib/base-path";

export function KitView() {
  const band = useBand();
  const logos = useAssets("logo");
  const photos = useAssets("photo");
  const members = band.data?.members ?? [];

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-8 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Band kit</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Your logos and photos are stored exactly as uploaded, fingerprinted with SHA-256, and placed into flyers without any
          stretching or regeneration. Crops, masks and colour treatments happen at render time; the originals never change.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="space-y-6">
          <BandCard band={band.data?.band} loading={band.loading} onSaved={(b) => band.setData((d) => (d ? { ...d, band: b } : d))} />
          <MembersCard members={members} loading={band.loading} onChange={(m) => band.setData((d) => (d ? { ...d, members: m } : d))} />
        </div>
        <div className="space-y-6">
          <AssetSection kind="logo" state={logos} members={members} />
          <AssetSection kind="photo" state={photos} members={members} />
        </div>
      </div>
    </div>
  );
}

function BandCard({ band, loading, onSaved }: { band?: Band; loading: boolean; onSaved: (b: Band) => void }) {
  const [draft, setDraft] = useState<Band>({ name: "", genre: "", hometown: "" });
  const [saving, setSaving] = useState(false);
  const [venuesText, setVenuesText] = useState("");
  const [prevBand, setPrevBand] = useState<Band | undefined>(undefined);
  if (band !== prevBand) {
    setPrevBand(band);
    if (band) {
      setDraft(band);
      setVenuesText((band.noTrailerVenues ?? []).join("\n"));
    }
  }
  const venues = venuesText.split("\n").map((v) => v.trim()).filter(Boolean);
  const dirty = band && JSON.stringify({ ...band, noTrailerVenues: band.noTrailerVenues ?? [] }) !== JSON.stringify({ ...draft, noTrailerVenues: venues });
  const save = async () => {
    setSaving(true);
    try {
      onSaved(await api<Band>("/api/band", { method: "PUT", json: { ...draft, noTrailerVenues: venues } }));
      toast.success("Band details saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>The band</CardTitle>
        <CardDescription>Used when there&apos;s no logo, to steer concepts, and to plan gig schedules.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <Skeleton className="h-32" />
        ) : (
          <>
            <Field label="Band name">
              <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="The Midnight Static" />
            </Field>
            <Field label="Genre / sound" hint="Concepts lean on this, e.g. 'garage soul', 'twangy indie'.">
              <Input value={draft.genre} onChange={(e) => setDraft({ ...draft, genre: e.target.value })} placeholder="Garage rock" />
            </Field>
            <Field label="Hometown">
              <Input value={draft.hometown} onChange={(e) => setDraft({ ...draft, hometown: e.target.value })} placeholder="Richmond, VA" />
            </Field>
            <Field label="Home address" hint="Where the band leaves from. Gig drive times are estimated from here.">
              <Input value={draft.homeAddress ?? ""} onChange={(e) => setDraft({ ...draft, homeAddress: e.target.value })} placeholder="123 Main St, Louisville, KY" />
            </Field>
            <Field label="Venues without the trailer" hint="One per line. Everywhere else the schedule assumes the equipment trailer.">
              <Textarea value={venuesText} onChange={(e) => setVenuesText(e.target.value)} placeholder="Stevie Ray's" className="min-h-16" />
            </Field>
            <Button onClick={save} disabled={!dirty || saving || !draft.name.trim()} className="w-full">
              Save
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function MembersCard({ members, loading, onChange }: { members: Member[]; loading: boolean; onChange: (m: Member[]) => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [editing, setEditing] = useState<Member | null>(null);
  const add = async () => {
    if (!name.trim()) return;
    try {
      onChange(await api<Member[]>("/api/members", { method: "POST", json: { name, role } }));
      setName("");
      setRole("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not add");
    }
  };
  const saveEdit = async () => {
    if (!editing) return;
    try {
      onChange(await api<Member[]>(`/api/members/${editing.id}`, { method: "PATCH", json: { name: editing.name, role: editing.role } }));
      setEditing(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save");
    }
  };
  const remove = async (id: string) => {
    try {
      onChange(await api<Member[]>(`/api/members/${id}`, { method: "DELETE" }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not remove");
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
        <CardDescription>Tag individual photos so you can feature anyone on demand.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <Skeleton className="h-20" />
        ) : (
          <ul className="divide-y divide-border/60">
            {members.length === 0 && <li className="py-2 text-sm text-muted-foreground">No members yet.</li>}
            {members.map((m) =>
              editing?.id === m.id ? (
                <li key={m.id} className="flex gap-2 py-2">
                  <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="h-8" />
                  <Input value={editing.role} onChange={(e) => setEditing({ ...editing, role: e.target.value })} className="h-8" placeholder="Role" />
                  <Button size="sm" onClick={saveEdit}>
                    Save
                  </Button>
                </li>
              ) : (
                <li key={m.id} className="group flex items-center justify-between py-2 text-sm">
                  <span>
                    {m.name} {m.role && <span className="text-muted-foreground">· {m.role}</span>}
                  </span>
                  <span className="flex gap-1 opacity-60 group-hover:opacity-100">
                    <Button size="icon-xs" variant="ghost" onClick={() => setEditing(m)} aria-label="Edit">
                      <Pencil />
                    </Button>
                    <Button size="icon-xs" variant="ghost" onClick={() => remove(m.id)} aria-label="Remove">
                      <X />
                    </Button>
                  </span>
                </li>
              ),
            )}
          </ul>
        )}
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void add();
          }}
        >
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className="h-8" />
          <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role" className="h-8" />
          <Button type="submit" size="sm" disabled={!name.trim()}>
            <Plus /> Add
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function AssetSection({
  kind,
  state,
  members,
}: {
  kind: "logo" | "photo";
  state: ReturnType<typeof useAssets>;
  members: Member[];
}) {
  const [uploadKind, setUploadKind] = useState<PhotoKind>("group");
  const [filter, setFilter] = useState<string>("all");
  const [showArchived, setShowArchived] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const assets = useMemo(() => state.data ?? [], [state.data]);
  const visible = useMemo(
    () =>
      assets.filter((a) => {
        if (a.archived !== showArchived) return false;
        if (filter === "all") return true;
        if (filter.startsWith("m:")) return a.memberIds.includes(filter.slice(2));
        return a.photoKind === filter;
      }),
    [assets, filter, showArchived],
  );
  const archivedCount = assets.filter((a) => a.archived).length;
  const open = assets.find((a) => a.id === openId) ?? null;
  const upsert = (a: Asset) => state.setData((list) => (list ? (list.some((x) => x.id === a.id) ? list.map((x) => (x.id === a.id ? a : a.isPrimary && x.isPrimary ? { ...x, isPrimary: false } : x)) : [a, ...list]) : [a]));

  const isLogo = kind === "logo";
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>{isLogo ? "Logos" : "Photos"}</CardTitle>
          <CardDescription>
            {isLogo
              ? "Upload every version you use (stacked, horizontal, light and dark). SVG or transparent PNG works best."
              : "Group shots and individual portraits. Use the highest-resolution originals you have; print needs pixels."}
          </CardDescription>
        </div>
        {archivedCount > 0 && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch checked={showArchived} onCheckedChange={setShowArchived} /> Archived ({archivedCount})
          </label>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className={cn("grid gap-3", !isLogo && "sm:grid-cols-[180px_1fr]")}>
          {!isLogo && (
            <Field label="Upload as">
              <Choice value={uploadKind} onChange={setUploadKind} options={PHOTO_KINDS} />
            </Field>
          )}
          <UploadZone
            kind={kind}
            label={isLogo ? "Drop logo files or click to upload" : "Drop photos or click to upload"}
            hint="PNG, JPEG, WebP or SVG · up to 60 MB each · stored byte-for-byte"
            extraMeta={isLogo ? undefined : () => ({ photoKind: uploadKind })}
            onUploaded={(a) => {
              upsert(a);
              toast.success(`${a.name || "File"} uploaded and verified`);
            }}
          />
        </div>
        {!isLogo && assets.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {[{ value: "all", label: "All" }, ...PHOTO_KINDS, ...members.map((m) => ({ value: `m:${m.id}`, label: m.name }))].map((f) => (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className={cn("rounded-full border px-2.5 py-1 text-xs transition-colors", filter === f.value ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:text-foreground")}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
        {state.loading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="aspect-square" />
            ))}
          </div>
        ) : state.error ? (
          <p className="text-sm text-destructive">{state.error}</p>
        ) : visible.length === 0 ? (
          <p className="rounded-md bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
            {assets.length === 0 ? (isLogo ? "No logos yet. Without one, flyers set your band name in type." : "No photos yet. Flyers need at least one to feature the band.") : "Nothing matches this filter."}
          </p>
        ) : (
          <div className={cn("grid gap-3", isLogo ? "grid-cols-2 sm:grid-cols-3 xl:grid-cols-4" : "grid-cols-2 sm:grid-cols-3 xl:grid-cols-4")}>
            {visible.map((a) => (
              <button key={a.id} onClick={() => setOpenId(a.id)} className="group overflow-hidden rounded-lg border border-border/60 text-left transition-colors hover:border-foreground/40">
                <div className={cn("relative aspect-square", isLogo ? "checker" : "bg-muted")}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={withBase(`/api/assets/${a.id}/preview`)} alt={a.name} className={cn("absolute inset-0 h-full w-full", isLogo ? "object-contain p-4" : "object-cover")} loading="lazy" />
                  {a.isPrimary && (
                    <span className="absolute left-2 top-2 rounded-full bg-black/70 p-1">
                      <Star className="size-3 fill-amber-400 text-amber-400" />
                    </span>
                  )}
                </div>
                <div className="space-y-1 p-2.5">
                  <div className="truncate text-sm font-medium">{a.name || "Untitled"}</div>
                  <div className="flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
                    {a.photoKind && <Badge variant="secondary" className="h-4 px-1.5 text-[10px] capitalize">{a.photoKind}</Badge>}
                    <span>
                      {a.width}×{a.height}
                    </span>
                    <span>· {formatBytes(a.byteSize)}</span>
                  </div>
                  {a.memberIds.length > 0 && <div className="truncate text-[11px] text-muted-foreground">{a.memberIds.map((id) => members.find((m) => m.id === id)?.name).filter(Boolean).join(", ")}</div>}
                </div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
      <AssetDialog
        asset={open}
        members={members}
        open={!!open}
        onOpenChange={(o) => !o && setOpenId(null)}
        onChanged={upsert}
        onDeleted={(id) => state.setData((list) => list?.filter((x) => x.id !== id))}
      />
    </Card>
  );
}