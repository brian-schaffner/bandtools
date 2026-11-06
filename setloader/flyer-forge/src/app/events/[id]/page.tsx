import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { EventView } from "@/components/calendar/event-view";

export default function EventPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto mt-8 h-[520px] w-full max-w-[1450px]" />}>
      <EventView />
    </Suspense>
  );
}
