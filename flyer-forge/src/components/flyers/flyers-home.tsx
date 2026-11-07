"use client";

import Link from "next/link";
import { toast } from "sonner";
import { ArrowRight, Check, MoreHorizontal, Plus } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useAssets, useBand, useFetch } from "@/hooks/use-fetch";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/recipes";
import { FORMATS, type FormatId } from "@/lib/spec";
import type { Flyer } from "@/lib/types";
import { cn } from "@/lib/utils";
import { withBase } from "@/lib/base-path";

export function FlyersHome() {
  const flyers = useFetch<Flyer[]>("/api/flyers");
  const band = useBand();
  const logos = useAssets("logo");
  const photos = useAssets("photo");

  const steps = [
    { done: !!band.data?.band.name, label: "Name your band", href: "/kit" },
    { done: (logos.data?.length ?? 0) > 0, label: "Upload a logo", href: "/kit" },
    { done: (photos.data?.length ?? 0) > 0, label: "Upload band photos", href: "/kit" },
  ];
  const setupLoading = band.loading || logos.loading || photos.loading;
  const setupDone = steps.every((s) => s.done);

  const remove = async (id: string) => {
    try {
      await api(`/api/flyers/${id}`, { method: "DELETE" });
      flyers.setData((l) => l?.filter((f) => f.id !== id));
      toast.success("Flyer deleted");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not delete");
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-8 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{band.data?.band.name ? `${band.data.band.name} flyers` : "Flyers"}</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Concept first, then your real photo and logo layered in untouched. Every version is kept so you can branch, evolve and compare.
          </p>
        </div>
        <Link href="/flyers/new" className={buttonVariants({ size: "lg" })}>
          <Plus /> New flyer
        </Link>
      </div>

      {!setupLoading && !setupDone && (
        <div className="rounded-lg border border-border/60 bg-card p-5">
          <h2 className="font-medium">Set up your band kit</h2>
          <p className="mt-1 text-sm text-muted-foreground">You can design without these, but flyers get much better with your real logo and photos.</p>
          <ol className="mt-4 grid gap-2 sm:grid-cols-3">
            {steps.map((s, i) => (
              <li key={s.label}>
                <Link href={s.href} className={cn("flex items-center gap-3 rounded-md border px-3 py-2.5 text-sm transition-colors", s.done ? "border-emerald-500/30 text-muted-foreground" : "border-border hover:border-foreground/40")}>
                  <span className={cn("grid size-6 place-items-center rounded-full text-xs", s.done ? "bg-emerald-500/20 text-emerald-400" : "bg-muted")}>{s.done ? <Check className="size-3.5" /> : i + 1}</span>
                  <span className={cn(s.done && "line-through")}>{s.label}</span>
                  {!s.done && <ArrowRight className="ml-auto size-4 text-muted-foreground" />}
                </Link>
              </li>
            ))}
          </ol>
        </div>
      )}

      {flyers.loading ? (
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="aspect-[2/3]" />
          ))}
        </div>
      ) : flyers.error ? (
        <div className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
          {flyers.error}{" "}
          <Button variant="link" onClick={() => flyers.reload()}>
            Retry
          </Button>
        </div>
      ) : !flyers.data?.length ? (
        <div className="grid place-items-center rounded-lg border border-dashed border-border px-6 py-20 text-center">
          <div className="max-w-sm space-y-3">
            <h2 className="text-lg font-medium">No flyers yet</h2>
            <p className="text-sm text-muted-foreground">Enter the gig details, pick a design direction from three concepts, then layer in your photo and logo.</p>
            <Link href="/flyers/new" className={buttonVariants()}>
              Design your first flyer
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {flyers.data.map((f) => {
            const fmt = FORMATS[(f.format as FormatId) ?? f.brief.format] ?? FORMATS["poster-11x17"];
            return (
              <div key={f.id} className="group relative">
                <Link href={`/flyers/${f.id}`} className="block">
                  <div className="overflow-hidden rounded-md border border-border/60 bg-muted transition-colors group-hover:border-foreground/40" style={{ aspectRatio: `${fmt.w} / ${fmt.h}` }}>
                    {f.currentVersionId && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={withBase(`/api/flyers/${f.id}/versions/${f.currentVersionId}/thumb`)} alt={f.title} className="h-full w-full object-cover" loading="lazy" />
                    )}
                  </div>
                  <div className="mt-2 truncate text-sm font-medium">{f.title}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {[formatDate(f.brief.date), f.brief.venue].filter(Boolean).join(" · ") || "No date yet"} · {fmt.label.split(" · ")[0]}
                  </div>
                </Link>
                <div className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100">
                  <DropdownMenu>
                    <DropdownMenuTrigger render={<Button size="icon-sm" variant="secondary" aria-label="More" />}>
                      <MoreHorizontal />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem variant="destructive" onClick={() => remove(f.id)}>
                        Delete flyer
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
