/**
 * The band's gig scheduling rules: work back from the performance start through dead stage, setup and the drive,
 * then print the result in the group-text format the band uses.
 */

export const SCHEDULE_KINDS = ["travel", "arrive", "load-in", "soundcheck", "dead-stage", "doors", "support", "set", "curfew", "load-out", "other"] as const;
export type ScheduleKind = (typeof SCHEDULE_KINDS)[number];

export const RULES = {
  cushionMinutes: 15,
  /** Unloading, setup and sound check together; no separate sound check unless asked for. */
  setupMinutes: 120,
  deadStageMinutes: 30,
  /** Towing the equipment trailer runs slower than the car estimate. */
  trailerExtra: 0.1,
  roundWithinMinutes: 5,
};

export const DEFAULT_NO_TRAILER_VENUES = ["Stevie Ray's"];

export type TrailerSetting = "auto" | "yes" | "no";

export interface PlannedSlot {
  time: string;
  endTime: string;
  label: string;
  kind: ScheduleKind;
  notes: string;
}

export interface GigPlanInput {
  venue: string;
  showTime: string;
  endTime: string;
  trailer: TrailerSetting;
  driveMinutes: number | null;
}

export interface GigPlan {
  items: PlannedSlot[];
  trailer: boolean;
  /** Drive + trailer allowance + cushion, or null when the drive time is unknown. */
  travelMinutes: number | null;
  /** How each time was reached, for the screen only; never part of the texted schedule. */
  steps: string[];
  problems: string[];
}

export function parseClock(t: string): number | null {
  const m = t.trim().toLowerCase().replace(/\./g, "").match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?$/);
  if (!m) return null;
  let h = Number(m[1]);
  const min = Number(m[2] ?? 0);
  if (h > 23 || min > 59) return null;
  const ap = m[3];
  if (ap?.startsWith("p") && h < 12) h += 12;
  if (ap?.startsWith("a") && h === 12) h = 0;
  // Stored times are zero-padded 24h ("09:30"); a hand-typed bare "8" or "8:30" at a gig means PM.
  const stored = /^\d{2}:\d{2}$/.test(t.trim());
  if (!ap && !stored && h >= 1 && h <= 11) h += 12;
  return h * 60 + min;
}

export function fmtClock(mins: number) {
  const m = ((mins % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

const venueKey = (s: string) =>
  s
    .toLowerCase()
    .replace(/[’'`]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

/** The trailer goes to every gig except the venues on the band's no-trailer list, unless a gig says otherwise. */
export function usesTrailer(e: { venue: string; trailer: TrailerSetting }, noTrailerVenues: string[]): boolean {
  if (e.trailer === "yes") return true;
  if (e.trailer === "no") return false;
  const v = venueKey(e.venue);
  return !noTrailerVenues.some((n) => {
    const k = venueKey(n);
    return k !== "" && v.includes(k);
  });
}

/** Snap to :00/:15/:30/:45 only when within five minutes of one; otherwise keep the exact time. */
export function roundDeparture(exact: number): number {
  const q = Math.round(exact / 15) * 15;
  return Math.abs(exact - q) <= RULES.roundWithinMinutes ? q : exact;
}

export function travelMinutes(driveMinutes: number, trailer: boolean) {
  const towing = trailer ? Math.ceil(driveMinutes * RULES.trailerExtra) : 0;
  return { drive: driveMinutes, towing, cushion: RULES.cushionMinutes, total: driveMinutes + towing + RULES.cushionMinutes };
}

export function planGig(e: GigPlanInput, noTrailerVenues: string[]): GigPlan {
  const trailer = usesTrailer(e, noTrailerVenues);
  const show = parseClock(e.showTime);
  if (show == null) return { items: [], trailer, travelMinutes: null, steps: [], problems: ["Add the performance start time (Show) to build the schedule."] };
  let end = parseClock(e.endTime);
  if (end != null && end <= show) end += 1440;
  const deadStage = show - RULES.deadStageMinutes;
  const arrive = deadStage - RULES.setupMinutes;
  const items: PlannedSlot[] = [];
  const steps: string[] = [];
  const problems: string[] = [];
  let total: number | null = null;

  if (e.driveMinutes != null && e.driveMinutes >= 0) {
    const t = travelMinutes(e.driveMinutes, trailer);
    total = t.total;
    const exact = arrive - t.total;
    const depart = roundDeparture(exact);
    items.push({ time: fmtClock(depart), endTime: "", label: "Depart home", kind: "travel", notes: "" });
    steps.push(`Travel ${t.total} min = ${t.drive} min drive${t.towing ? ` + ${t.towing} min towing the trailer` : ""} + ${t.cushion} min cushion`);
    steps.push(
      depart === exact
        ? `Depart ${clock12(exact)} exactly (more than ${RULES.roundWithinMinutes} min from a quarter hour)`
        : `Depart ${clock12(exact)} rounded to ${clock12(depart)}`,
    );
  } else {
    problems.push("Drive time unknown, so there's no departure time. Estimate it from the band's home address or type it in.");
  }
  items.push({ time: fmtClock(arrive), endTime: "", label: "Arrive at venue", kind: "arrive", notes: "" });
  items.push({ time: fmtClock(arrive), endTime: fmtClock(deadStage), label: "Unload, setup & sound check", kind: "load-in", notes: "" });
  items.push({ time: fmtClock(deadStage), endTime: fmtClock(show), label: "Dead stage", kind: "dead-stage", notes: "" });
  items.push({ time: fmtClock(show), endTime: end != null ? fmtClock(end) : "", label: "PERFORMANCE", kind: "set", notes: "" });
  if (end != null) items.push({ time: fmtClock(end), endTime: "", label: "Teardown & load out", kind: "load-out", notes: "" });
  else problems.push("Add when the performance ends to schedule teardown.");
  steps.push(`Arrive ${clock12(arrive)}: ${RULES.setupMinutes / 60} h setup & sound check, then ${RULES.deadStageMinutes} min dead stage before the ${clock12(show)} start`);
  steps.push(trailer ? "Trailer: yes" : "Trailer: no");
  return { items, trailer, travelMinutes: total, steps, problems };
}

// ---------- the group-text format ----------

export const KIND_EMOJI: Record<ScheduleKind, string> = {
  travel: "🚗",
  arrive: "📍",
  "load-in": "🎤",
  soundcheck: "🎤",
  "dead-stage": "🔇",
  doors: "🚪",
  support: "🎵",
  set: "🎶",
  curfew: "⏰",
  "load-out": "📦",
  other: "📌",
};

function parts(mins: number) {
  const m = ((mins % 1440) + 1440) % 1440;
  const h = Math.floor(m / 60);
  return { hm: `${h % 12 || 12}:${String(m % 60).padStart(2, "0")}`, ap: h < 12 ? "AM" : "PM" };
}

export function clock12(mins: number) {
  const p = parts(mins);
  return `${p.hm} ${p.ap}`;
}

export function range12(a: number, b: number) {
  const pa = parts(a);
  const pb = parts(b);
  return pa.ap === pb.ap ? `${pa.hm}–${pb.hm} ${pb.ap}` : `${pa.hm} ${pa.ap}–${pb.hm} ${pb.ap}`;
}

function longDate(iso: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" });
}

/** The schedule exactly as it goes into the group text: heading, then one emoji line per activity, in order. */
export function scheduleText(
  heading: { bandName: string; venue: string; date: string },
  items: { time: string; endTime?: string; label: string; kind: ScheduleKind }[],
): string {
  const lines = [`🎸 ${(heading.bandName || "The band").toUpperCase()}`, `📍 ${heading.venue || "Venue TBA"}`, `📅 ${longDate(heading.date)}`];
  const order = (t: string) => {
    const v = parseClock(t);
    return v == null ? 9999 : v < 6 * 60 ? v + 1440 : v;
  };
  const sorted = items
    .map((it, i) => ({ it, i }))
    .sort((a, b) => order(a.it.time) - order(b.it.time) || a.i - b.i)
    .map(({ it }) => it);
  const body = sorted.map((it) => {
    const start = parseClock(it.time);
    const end = it.endTime ? parseClock(it.endTime) : null;
    const when = start == null ? "" : end != null && end !== start ? range12(start, end) : clock12(start);
    return `${KIND_EMOJI[it.kind] ?? KIND_EMOJI.other} ${when ? `${when} – ` : ""}${it.label}`;
  });
  return [lines.join("\n"), ...body].join("\n\n");
}
