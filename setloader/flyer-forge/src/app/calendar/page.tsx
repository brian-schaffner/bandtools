import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarView } from "@/components/calendar/calendar-view";

export const metadata = { title: "Calendar · Gig Flyer Studio" };

export default function CalendarPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto mt-8 h-[640px] w-full max-w-[1450px]" />}>
      <CalendarView />
    </Suspense>
  );
}
