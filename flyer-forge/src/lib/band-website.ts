import "server-only";
import { parseWebsiteListings, type WebsiteListing } from "@/lib/website-listings";

const DEFAULT_URL = "https://www.lindseylane.com/dates/";

/** The band website's gig listings; an empty list when the site is unreachable so a Facebook sync never fails on it. */
export async function fetchWebsiteListings(): Promise<WebsiteListing[]> {
  const url = process.env.GIG_CALENDAR_URL?.trim() || DEFAULT_URL;
  if (url === "off") return [];
  try {
    const res = await fetch(url, { headers: { "user-agent": "BandTools-FlyerForge/1.0" }, signal: AbortSignal.timeout(15_000), cache: "no-store" });
    if (!res.ok) return [];
    return parseWebsiteListings(await res.text());
  } catch {
    return [];
  }
}
