import type { Metadata } from "next";
import { ReferencesView } from "@/components/references/references-view";

export const metadata: Metadata = { title: "References · Gig Flyer Studio" };

export default function ReferencesPage() {
  return <ReferencesView />;
}
