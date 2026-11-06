import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { SetlistEditor } from "@/components/setlists/setlist-editor";

export default function SetlistPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto mt-8 h-96 w-full max-w-4xl" />}>
      <SetlistEditor />
    </Suspense>
  );
}
