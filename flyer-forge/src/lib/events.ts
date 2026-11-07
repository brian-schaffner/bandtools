import { z } from "zod";
import { BriefSchema, type Brief } from "./spec";
import { parseClock, SCHEDULE_KINDS, type ScheduleKind } from "./gig-schedule";

export { fmtClock, parseClock, SCHEDULE_KINDS, type ScheduleKind } from "./gig-schedule";

export const EVENT_STATUSES = ["tentative", "confirmed", "cancelled"] as const;
export type EventStatus = (typeof EVENT_STATUSES)[number];

const text = (max = 500) => z.string().trim().max(max).default("");

export const EventFieldsSchema = z.object({
  title: text(160),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Date must be YYYY-MM-DD"),
  status: z.enum(EVENT_STATUSES).default("confirmed"),
  venue: text(160),
  city: text(160),
  address: text(300),
  doors: text(40),
  showTime: text(40),
  endTime: text(40),
  price: text(80),
  ages: text(40),
  support: z.array(z.string().trim().max(120)).max(12).default([]),
  tickets: text(300),
  contactName: text(120),
  contactPhone: text(60),
  contactEmail: text(160),
  deal: text(300),
  notes: text(4000),
  /** Minutes of driving from the band's home to the venue; null until estimated or typed in. */
  driveMinutes: z.number().int().min(0).max(24 * 60).nullable().default(null),
  trailer: z.enum(["auto", "yes", "no"]).default("auto"),
});
export type EventFields = z.infer<typeof EventFieldsSchema>;

export const SCHEDULE_LABELS: Record<ScheduleKind, string> = {
  travel: "Travel",
  arrive: "Arrive",
  "load-in": "Setup",
  soundcheck: "Soundcheck",
  "dead-stage": "Dead stage",
  doors: "Doors",
  support: "Support set",
  set: "Our set",
  curfew: "Curfew",
  "load-out": "Load-out",
  other: "Other",
};

export const ScheduleItemSchema = z.object({
  id: z.string().optional(),
  time: z.string().trim().max(20).default(""),
  endTime: z.string().trim().max(20).default(""),
  label: z.string().trim().min(1).max(160),
  kind: z.enum(SCHEDULE_KINDS).default("other"),
  notes: z.string().trim().max(1000).default(""),
});
export type ScheduleItem = z.infer<typeof ScheduleItemSchema> & { id: string };

export const SetlistItemSchema = z.object({
  type: z.enum(["song", "section"]).default("song"),
  title: z.string().trim().min(1).max(200),
  duration: z.number().int().min(0).max(60 * 60).nullable().default(null),
  key: z.string().trim().max(20).default(""),
  notes: z.string().trim().max(300).default(""),
  segue: z.boolean().default(false),
});
export type SetlistItem = z.infer<typeof SetlistItemSchema>;

export interface CalendarEvent extends EventFields {
  id: string;
  externalUid: string | null;
  createdAt: string;
  updatedAt: string;
  flyerCount?: number;
  setlistCount?: number;
  coverFlyer?: { id: string; versionId: string } | null;
}

export interface Setlist {
  id: string;
  eventId: string | null;
  name: string;
  notes: string;
  items: SetlistItem[];
  source: "manual" | "paste" | "file" | "copy";
  createdAt: string;
  updatedAt: string;
  event?: { id: string; date: string; venue: string; title: string } | null;
}

export interface SongStat {
  title: string;
  count: number;
  lastDate: string | null;
}

export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function isPast(e: { date: string }) {
  return e.date < todayIso();
}

export function eventLabel(e: { title: string; venue: string; city?: string }) {
  return e.title || e.venue || "Untitled gig";
}

export function statusLabel(e: { status: EventStatus; date: string }) {
  if (e.status === "cancelled") return "Cancelled";
  if (isPast(e)) return e.status === "tentative" ? "Didn't confirm" : "Played";
  return e.status === "tentative" ? "Hold" : "Confirmed";
}

/* ---------- Flyer brief <-> event ---------- */

export function eventToBrief(e: EventFields, base?: Partial<Brief>): Brief {
  return BriefSchema.parse({
    ...base,
    headline: e.title || base?.headline || "",
    date: e.date,
    doors: e.doors,
    showTime: e.showTime,
    endTime: e.endTime,
    venue: e.venue,
    city: e.city,
    address: e.address,
    price: e.price,
    ages: e.ages,
    support: e.support,
    tickets: e.tickets,
  });
}

export function briefToEventFields(b: Brief): EventFields {
  return EventFieldsSchema.parse({
    title: b.headline,
    date: b.date,
    venue: b.venue,
    city: b.city,
    doors: b.doors,
    showTime: b.showTime,
    endTime: b.endTime,
    address: b.address,
    price: b.price,
    ages: b.ages,
    support: b.support,
    tickets: b.tickets,
  });
}

const BRIEF_FIELDS: { key: keyof Brief & keyof EventFields; label: string }[] = [
  { key: "date", label: "Date" },
  { key: "venue", label: "Venue" },
  { key: "city", label: "City" },
  { key: "address", label: "Address" },
  { key: "doors", label: "Doors" },
  { key: "showTime", label: "Show time" },
  { key: "endTime", label: "Ends" },
  { key: "price", label: "Price" },
  { key: "ages", label: "Ages" },
  { key: "support", label: "Support" },
  { key: "tickets", label: "Tickets" },
];

/** Fields where a flyer's printed details no longer match the calendar event. */
export function briefMismatches(e: EventFields, b: Brief): { label: string; flyer: string; event: string }[] {
  const norm = (v: unknown) => (Array.isArray(v) ? v.join(", ") : String(v ?? "")).trim();
  return BRIEF_FIELDS.filter((f) => norm(e[f.key]).toLowerCase() !== norm(b[f.key]).toLowerCase()).map((f) => ({
    label: f.label,
    flyer: norm(b[f.key]) || "—",
    event: norm(e[f.key]) || "—",
  }));
}

/* ---------- Logistics ---------- */

export function sortTime(t: string) {
  const v = parseClock(t);
  if (v == null) return 9999;
  return v < 6 * 60 ? v + 1440 : v;
}

/* ---------- Set lists ---------- */

export function parseDuration(s: string): number | null {
  const m = s.trim().match(/^(\d{1,2}):(\d{2})$/);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

export function formatDuration(sec: number | null | undefined) {
  if (sec == null) return "";
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export function totalDuration(items: SetlistItem[]) {
  const songs = items.filter((i) => i.type === "song");
  const known = songs.filter((i) => i.duration != null);
  return { songs: songs.length, seconds: known.reduce((a, i) => a + (i.duration ?? 0), 0), unknown: songs.length - known.length };
}

const SECTION_RE = /^(?:#+\s*)?(set\s*(?:\d+|one|two|three|i{1,3})|encore\s*\d*|acoustic(?: set)?|intro|outro)\s*:?\s*$/i;

function splitCsv(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (q && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else q = !q;
    } else if (ch === "," && !q) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

/**
 * Reads set lists as bands actually write them: numbered or bulleted lines,
 * "Set 1"/"Encore" headers, durations like 3:45, keys like [E] or (key: Am),
 * and "->" / ">" for segues. CSV with a header row (title, duration, key, notes) also works.
 */
export function parseSetlistText(raw: string): SetlistItem[] {
  const lines = raw.replace(/\r/g, "").split("\n").map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return [];

  const header = splitCsv(lines[0].toLowerCase());
  if (lines[0].includes(",") && header.some((h) => /^(title|song|name)$/.test(h))) {
    const col = (re: RegExp) => header.findIndex((h) => re.test(h));
    const ti = col(/^(title|song|name)$/);
    const di = col(/^(duration|length|time)$/);
    const ki = col(/^key$/);
    const ni = col(/^(notes?|comments?)$/);
    return lines
      .slice(1)
      .map((l) => splitCsv(l))
      .filter((c) => c[ti])
      .map((c) => {
        const title = c[ti];
        if (SECTION_RE.test(title)) return SetlistItemSchema.parse({ type: "section", title: title.replace(/:$/, "") });
        return SetlistItemSchema.parse({
          title,
          duration: di >= 0 ? parseDuration(c[di] ?? "") : null,
          key: ki >= 0 ? (c[ki] ?? "") : "",
          notes: ni >= 0 ? (c[ni] ?? "") : "",
        });
      });
  }

  const items: SetlistItem[] = [];
  for (let line of lines) {
    if (/^[-=_*~]{3,}$/.test(line)) continue;
    if (SECTION_RE.test(line)) {
      items.push(SetlistItemSchema.parse({ type: "section", title: line.replace(/^#+\s*/, "").replace(/:$/, "") }));
      continue;
    }
    line = line.replace(/^(?:\d{1,3}\s*[.)\]:-]\s*|[-*•·]\s+)/, "");
    let segue = false;
    if (/\s*(?:->|→|>)\s*$/.test(line)) {
      segue = true;
      line = line.replace(/\s*(?:->|→|>)\s*$/, "");
    }
    let duration: number | null = null;
    line = line.replace(/[\s(\[-]*\b(\d{1,2}:\d{2})\b[)\]]?\s*$/, (_, d: string) => {
      duration = parseDuration(d);
      return "";
    });
    let key = "";
    line = line.replace(/\s*[(\[]\s*(?:key\s*(?:of)?\s*:?\s*|in\s+)?([A-G](?:#|b|♯|♭)?(?:m|min|maj)?)\s*[)\]]\s*/i, (_, k: string) => {
      key = k;
      return " ";
    });
    line = line.replace(/\s*[-–—|]\s*key\s*:?\s*([A-G](?:#|b)?m?)\s*$/i, (_, k: string) => {
      key = k;
      return "";
    });
    let notes = "";
    line = line.replace(/\s*[(\[]([^)\]]{1,120})[)\]]\s*$/, (_, n: string) => {
      notes = n.trim();
      return "";
    });
    const title = line.replace(/\s+/g, " ").replace(/[\s,;|–—-]+$/, "").trim();
    if (!title) continue;
    items.push(SetlistItemSchema.parse({ title, duration, key, notes, segue }));
  }
  return items;
}

export function songNumbers(items: SetlistItem[]): (number | null)[] {
  let n = 0;
  return items.map((i) => (i.type === "song" ? ++n : null));
}

export function setlistToText(items: SetlistItem[]) {
  let n = 0;
  return items
    .map((i) => {
      if (i.type === "section") return `\n${i.title.toUpperCase()}`;
      n += 1;
      const bits = [`${n}. ${i.title}`];
      if (i.key) bits.push(`[${i.key}]`);
      if (i.duration != null) bits.push(formatDuration(i.duration));
      if (i.notes) bits.push(`(${i.notes})`);
      return bits.join(" ") + (i.segue ? " ->" : "");
    })
    .join("\n")
    .trim();
}

export function songKey(title: string) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/* ---------- iCalendar ---------- */

const icsEscape = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");

function foldLine(line: string) {
  const out: string[] = [];
  let rest = line;
  while (rest.length > 60) {
    out.push(rest.slice(0, 60));
    rest = " " + rest.slice(60);
  }
  out.push(rest);
  return out.join("\r\n");
}

export function buildIcs(events: (CalendarEvent & { schedule?: ScheduleItem[] })[], bandName: string) {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Gig Flyer Studio//Calendar//EN", "CALSCALE:GREGORIAN", `X-WR-CALNAME:${icsEscape(bandName || "Band")} gigs`];
  for (const e of events) {
    const day = e.date.replace(/-/g, "");
    const next = new Date(`${e.date}T00:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    const end = next.toISOString().slice(0, 10).replace(/-/g, "");
    const desc = [
      e.support.length ? `With ${e.support.join(", ")}` : "",
      [e.doors && `Doors ${e.doors}`, e.showTime && `Show ${e.showTime}`, e.price, e.ages].filter(Boolean).join(" · "),
      ...(e.schedule ?? []).map((s) => `${s.time}${s.endTime ? `–${s.endTime}` : ""} ${s.label}${s.notes ? ` (${s.notes})` : ""}`),
      e.contactName || e.contactPhone ? `Contact: ${[e.contactName, e.contactPhone, e.contactEmail].filter(Boolean).join(" ")}` : "",
      e.deal ? `Deal: ${e.deal}` : "",
      e.tickets ? `Tickets: ${e.tickets}` : "",
      e.notes,
    ]
      .filter(Boolean)
      .join("\n");
    lines.push(
      "BEGIN:VEVENT",
      `UID:${e.id}@gig-flyer-studio`,
      `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${day}`,
      `DTEND;VALUE=DATE:${end}`,
      foldLine(`SUMMARY:${icsEscape(`${bandName ? `${bandName} @ ` : ""}${e.venue || e.title || "Gig"}${e.title && e.venue ? ` — ${e.title}` : ""}`)}`),
      foldLine(`LOCATION:${icsEscape([e.venue, e.address || e.city].filter(Boolean).join(", "))}`),
      foldLine(`DESCRIPTION:${icsEscape(desc)}`),
      `STATUS:${e.status === "cancelled" ? "CANCELLED" : e.status === "tentative" ? "TENTATIVE" : "CONFIRMED"}`,
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  return lines.join("\r\n") + "\r\n";
}

export interface IcsEvent {
  uid: string;
  date: string;
  time: string;
  summary: string;
  location: string;
  description: string;
  status: EventStatus;
}

export function parseIcs(raw: string): IcsEvent[] {
  const unfolded = raw.replace(/\r\n[ \t]/g, "").replace(/\n[ \t]/g, "").split(/\r?\n/);
  const unescape = (s: string) => s.replace(/\\n/gi, "\n").replace(/\\([,;\\])/g, "$1");
  const out: IcsEvent[] = [];
  let cur: Record<string, string> | null = null;
  for (const line of unfolded) {
    if (line === "BEGIN:VEVENT") cur = {};
    else if (line === "END:VEVENT" && cur) {
      const start = cur.DTSTART ?? "";
      const m = start.match(/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?/);
      if (m) {
        const st = (cur.STATUS ?? "").toUpperCase();
        out.push({
          uid: cur.UID || `${start}-${cur.SUMMARY ?? ""}`,
          date: `${m[1]}-${m[2]}-${m[3]}`,
          time: m[4] ? `${m[4]}:${m[5]}` : "",
          summary: unescape(cur.SUMMARY ?? ""),
          location: unescape(cur.LOCATION ?? ""),
          description: unescape(cur.DESCRIPTION ?? ""),
          status: st === "CANCELLED" ? "cancelled" : st === "TENTATIVE" ? "tentative" : "confirmed",
        });
      }
      cur = null;
    } else if (cur) {
      const i = line.indexOf(":");
      if (i > 0) {
        const name = line.slice(0, i).split(";")[0].toUpperCase();
        cur[name] = line.slice(i + 1);
      }
    }
  }
  return out;
}
