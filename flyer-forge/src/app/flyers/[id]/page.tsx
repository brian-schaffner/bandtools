import { Suspense } from "react";
import type { Metadata } from "next";
import { FlyerEditor } from "@/components/editor/flyer-editor";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Editor · Gig Flyer Studio" };

export default function FlyerPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto mt-6 aspect-[2/3] w-full max-w-xl" />}>
      <FlyerEditor />
    </Suspense>
  );
}
