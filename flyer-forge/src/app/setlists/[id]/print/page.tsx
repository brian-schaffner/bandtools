import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { SetlistPrint } from "@/components/setlists/setlist-print";

export default function SetlistPrintPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto mt-10 h-[80vh] max-w-2xl" />}>
      <SetlistPrint />
    </Suspense>
  );
}
