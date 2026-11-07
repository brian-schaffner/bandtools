/** Listings on the band's own website calendar (WordPress Modern Events Calendar), which carry street addresses Facebook doesn't. */
export interface WebsiteListing {
  date: string;
  title: string;
  start: string;
  end: string;
  address: string;
  city: string;
}

const MONTHS: Record<string, number> = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

function decode(s: string) {
  return s
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&apos;|&#039;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** "Nov 07 2026" → "2026-11-07". */
function isoDate(label: string): string {
  const m = /^([A-Za-z]{3})[a-z]*\s+(\d{1,2})\s+(\d{4})$/.exec(label.trim());
  const month = m ? MONTHS[m[1].toLowerCase()] : undefined;
  if (!m || !month) return "";
  return `${m[3]}-${String(month).padStart(2, "0")}-${m[2].padStart(2, "0")}`;
}

/** Street address embedded in a listing title, e.g. "Ernie's 104 Taylorsville Rd, Bloomfield, KY 40008". */
export function extractAddress(title: string): string {
  const head = /^(.*\b\d{5})\b/.exec(title)?.[1];
  if (!head) return "";
  const beforeComma = head.split(",", 1)[0];
  let start = -1;
  for (const m of beforeComma.matchAll(/(?<![\w-])\d+\s+[A-Za-z]/g)) start = m.index;
  return start < 0 ? "" : head.slice(start).replace(/\s+/g, " ").trim();
}

/** "9702 Old Bardstown Rd, Louisville, KY 40291" → "Louisville, KY". */
export function cityFromAddress(address: string): string {
  const parts = address.split(",").map((p) => p.trim());
  if (parts.length < 3) return "";
  const state = /^([A-Z]{2})\b/.exec(parts[parts.length - 1])?.[1];
  return state ? `${parts[parts.length - 2]}, ${state}` : "";
}

export function parseWebsiteListings(html: string): WebsiteListing[] {
  const out: WebsiteListing[] = [];
  for (const [, article] of html.matchAll(/<article[^>]*class="[^"]*mec-event-article[^"]*"[^>]*>([\s\S]*?)<\/article>/g)) {
    const date = isoDate(/mec-start-date-label">([^<]+)/.exec(article)?.[1] ?? "");
    const title = decode(/mec-event-title[^>]*>[\s\S]*?<a[^>]*>([^<]+)/.exec(article)?.[1] ?? "");
    if (!date || !title) continue;
    const address = extractAddress(title);
    out.push({
      date,
      title,
      start: decode(/mec-start-time">([^<]+)/.exec(article)?.[1] ?? ""),
      end: decode(/mec-end-time">([^<]+)/.exec(article)?.[1] ?? ""),
      address,
      city: cityFromAddress(address),
    });
  }
  return out;
}

const words = (s: string) =>
  new Set(
    s
      .toLowerCase()
      .replace(/[’']/g, "")
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length > 2 && !["the", "and", "presents", "band", "lindsey", "lane"].includes(w)),
  );

/** The website listing for a gig: same date, and the venue shares a word with the listing title. */
export function matchListing(gig: { date: string; venue: string; title: string }, listings: WebsiteListing[]): WebsiteListing | null {
  const sameDay = listings.filter((l) => l.date === gig.date);
  if (!sameDay.length) return null;
  const wanted = words(`${gig.venue} ${gig.title}`);
  let best: WebsiteListing | null = null;
  let bestScore = 0;
  for (const l of sameDay) {
    const score = [...words(l.title)].filter((w) => wanted.has(w)).length;
    if (score > bestScore) {
      best = l;
      bestScore = score;
    }
  }
  return best;
}
