"use client";

import { useParams } from "next/navigation";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBand, useFetch } from "@/hooks/use-fetch";
import { formatDate } from "@/lib/recipes";
import { songNumbers, type Setlist } from "@/lib/events";

export function SetlistPrint() {
  const { id } = useParams<{ id: string }>();
  const q = useFetch<Setlist>(`/api/setlists/${id}`);
  const band = useBand();
  if (q.error) return <p className="p-10 text-center text-sm text-destructive">{q.error}</p>;
  if (!q.data) return <Skeleton className="mx-auto mt-10 h-[80vh] max-w-2xl" />;
  const s = q.data;
  const songs = s.items.filter((i) => i.type === "song").length;
  const size = songs > 22 ? "text-2xl" : songs > 16 ? "text-3xl" : "text-4xl";
  const numbers = songNumbers(s.items);
  return (
    <div className="min-h-screen bg-neutral-200 py-8 print:bg-white print:py-0">
      <div className="mx-auto mb-4 flex max-w-[8.5in] justify-end px-4 print:hidden">
        <Button onClick={() => window.print()}>
          <Printer /> Print
        </Button>
      </div>
      <article className="mx-auto min-h-[11in] max-w-[8.5in] bg-white p-[0.6in] text-black shadow-lg print:min-h-0 print:p-[0.4in] print:shadow-none">
        <header className="mb-6 flex items-baseline justify-between border-b-4 border-black pb-2 text-sm font-semibold uppercase tracking-wider">
          <span>{band.data?.band.name || s.name}</span>
          <span>{s.event ? `${s.event.venue} · ${formatDate(s.event.date)}` : s.name}</span>
        </header>
        <ol className="space-y-1">
          {s.items.map((it, i) =>
            it.type === "section" ? (
              <li key={i} className="mt-4 border-t-2 border-black pt-2 text-lg font-black uppercase tracking-[0.2em]">
                {it.title}
              </li>
            ) : (
              <li key={i} className={`flex items-baseline gap-4 font-black uppercase leading-tight ${size}`} style={{ fontFamily: "'Archivo Black', 'Oswald', sans-serif" }}>
                <span className="w-10 shrink-0 text-right text-base font-bold text-neutral-500">{numbers[i]}</span>
                <span className="flex-1">
                  {it.title}
                  {it.segue && " →"}
                </span>
                {it.key && <span className="text-base font-bold normal-case text-neutral-600">{it.key}</span>}
              </li>
            ),
          )}
        </ol>
      </article>
    </div>
  );
}
