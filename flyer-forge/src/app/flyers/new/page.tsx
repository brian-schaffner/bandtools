import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { NewFlyer } from "@/components/flyers/new-flyer";

export const metadata: Metadata = { title: "New flyer · Gig Flyer Studio" };

export default function NewFlyerPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto mt-8 h-96 w-full max-w-3xl" />}>
      <NewFlyer />
    </Suspense>
  );
}
