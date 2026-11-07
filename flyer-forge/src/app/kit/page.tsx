import type { Metadata } from "next";
import { KitView } from "@/components/kit/kit-view";

export const metadata: Metadata = { title: "Band kit · Gig Flyer Studio" };

export default function KitPage() {
  return <KitView />;
}
