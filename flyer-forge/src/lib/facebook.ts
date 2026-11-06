import "server-only";
import type { FacebookEvent } from "./facebook-map";

const GRAPH = "https://graph.facebook.com/v21.0";
const FIELDS = "id,name,description,start_time,end_time,is_canceled,ticket_uri,place{name,location{street,city,state,zip}},event_times{id,start_time,end_time}";
const MAX_PAGES = 10;

export function facebookConfig() {
  const pageId = process.env.FACEBOOK_PAGE_ID?.trim() ?? "";
  const token = process.env.FACEBOOK_PAGE_ACCESS_TOKEN?.trim() ?? "";
  return pageId && token ? { pageId, token } : null;
}

export function bandTimeZone() {
  const tz = process.env.GIG_CALENDAR_TIMEZONE?.trim() || "America/Kentucky/Louisville";
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return tz;
  } catch {
    return "America/Kentucky/Louisville";
  }
}

/** Upcoming Page events, all pages. Errors carry Facebook's message but never the token-bearing URL. */
export async function fetchFacebookEvents(cfg: { pageId: string; token: string }): Promise<FacebookEvent[]> {
  const query = new URLSearchParams({ fields: FIELDS, time_filter: "upcoming", limit: "100", access_token: cfg.token });
  let url: string | undefined = `${GRAPH}/${encodeURIComponent(cfg.pageId)}/events?${query}`;
  const rows: FacebookEvent[] = [];
  for (let page = 0; url && page < MAX_PAGES; page++) {
    let res: Response;
    try {
      res = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(20_000) });
    } catch {
      throw new Error("Could not reach Facebook");
    }
    const body = (await res.json().catch(() => null)) as { data?: FacebookEvent[]; paging?: { next?: string }; error?: { message?: string } } | null;
    if (!res.ok || !body) throw new Error(`Facebook said: ${body?.error?.message ?? `HTTP ${res.status}`}`);
    rows.push(...(body.data ?? []));
    url = body.paging?.next;
  }
  return rows;
}
