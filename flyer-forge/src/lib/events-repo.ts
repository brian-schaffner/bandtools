import "server-only";
import { sql } from "./db";
import { newId } from "./repo";
import { EventFieldsSchema, sortTime, type CalendarEvent, type EventFields, type ScheduleItem, type Setlist, type SetlistItem } from "./events";

type Row = Record<string, unknown>;

const iso = (v: unknown) => (v instanceof Date ? v.toISOString() : String(v));
const json = <T,>(v: unknown, fallback: T): T => {
  if (v == null) return fallback;
  if (typeof v === "string") {
    try {
      return JSON.parse(v) as T;
    } catch {
      return fallback;
    }
  }
  return v as T;
};

export function mapEvent(r: Row): CalendarEvent {
  return {
    id: String(r.id),
    title: String(r.title ?? ""),
    date: String(r.date),
    status: (r.status as CalendarEvent["status"]) ?? "confirmed",
    venue: String(r.venue ?? ""),
    city: String(r.city ?? ""),
    address: String(r.address ?? ""),
    doors: String(r.doors ?? ""),
    showTime: String(r.show_time ?? ""),
    endTime: String(r.end_time ?? ""),
    price: String(r.price ?? ""),
    ages: String(r.ages ?? ""),
    support: json<string[]>(r.support, []),
    tickets: String(r.tickets ?? ""),
    contactName: String(r.contact_name ?? ""),
    contactPhone: String(r.contact_phone ?? ""),
    contactEmail: String(r.contact_email ?? ""),
    deal: String(r.deal ?? ""),
    notes: String(r.notes ?? ""),
    externalUid: (r.external_uid as string) ?? null,
    createdAt: iso(r.created_at),
    updatedAt: iso(r.updated_at),
    ...(r.flyer_count != null ? { flyerCount: Number(r.flyer_count) } : {}),
    ...(r.setlist_count != null ? { setlistCount: Number(r.setlist_count) } : {}),
    ...(r.cover_flyer_id ? { coverFlyer: { id: String(r.cover_flyer_id), versionId: String(r.cover_version_id) } } : {}),
  };
}

export function mapSchedule(r: Row): ScheduleItem {
  return {
    id: String(r.id),
    time: String(r.time ?? ""),
    label: String(r.label),
    kind: r.kind as ScheduleItem["kind"],
    notes: String(r.notes ?? ""),
  };
}

export function mapSetlist(r: Row): Setlist {
  return {
    id: String(r.id),
    eventId: (r.event_id as string) ?? null,
    name: String(r.name),
    notes: String(r.notes ?? ""),
    items: json<SetlistItem[]>(r.items, []),
    source: (r.source as Setlist["source"]) ?? "manual",
    createdAt: iso(r.created_at),
    updatedAt: iso(r.updated_at),
    event: r.event_date ? { id: String(r.event_id), date: String(r.event_date), venue: String(r.event_venue ?? ""), title: String(r.event_title ?? "") } : null,
  };
}

const FIELD_COLS: [keyof EventFields, string][] = [
  ["title", "title"],
  ["date", "date"],
  ["status", "status"],
  ["venue", "venue"],
  ["city", "city"],
  ["address", "address"],
  ["doors", "doors"],
  ["showTime", "show_time"],
  ["endTime", "end_time"],
  ["price", "price"],
  ["ages", "ages"],
  ["support", "support"],
  ["tickets", "tickets"],
  ["contactName", "contact_name"],
  ["contactPhone", "contact_phone"],
  ["contactEmail", "contact_email"],
  ["deal", "deal"],
  ["notes", "notes"],
];

const colValue = (k: keyof EventFields, v: unknown) => (k === "support" ? JSON.stringify(v ?? []) : v);

export async function insertEvent(fields: EventFields, externalUid: string | null = null): Promise<CalendarEvent> {
  const id = newId("event");
  const cols = FIELD_COLS.map(([, c]) => c);
  const vals = FIELD_COLS.map(([k]) => colValue(k, fields[k]));
  const placeholders = FIELD_COLS.map(([k], i) => (k === "support" ? `$${i + 2}::jsonb` : `$${i + 2}`));
  const rows = await sql(
    `insert into events (id, ${cols.join(", ")}, external_uid) values ($1, ${placeholders.join(", ")}, $${cols.length + 2}) returning *`,
    [id, ...vals, externalUid],
  );
  return mapEvent(rows[0]);
}

export async function updateEvent(id: string, patch: Partial<EventFields>): Promise<CalendarEvent | null> {
  const entries = FIELD_COLS.filter(([k]) => patch[k] !== undefined);
  if (!entries.length) return getEvent(id);
  const sets = entries.map(([k, c], i) => (k === "support" ? `${c} = $${i + 2}::jsonb` : `${c} = $${i + 2}`));
  const rows = await sql(`update events set ${sets.join(", ")}, updated_at = now() where id = $1 returning *`, [
    id,
    ...entries.map(([k]) => colValue(k, patch[k])),
  ]);
  return rows[0] ? mapEvent(rows[0]) : null;
}

export async function getEvent(id: string): Promise<CalendarEvent | null> {
  const rows = await sql("select * from events where id = $1", [id]);
  return rows[0] ? mapEvent(rows[0]) : null;
}

export async function listEvents(): Promise<CalendarEvent[]> {
  const rows = await sql(
    `select e.*,
       (select count(*) from flyers f where f.event_id = e.id and not f.archived) as flyer_count,
       (select count(*) from setlists s where s.event_id = e.id) as setlist_count,
       c.id as cover_flyer_id, c.current_version_id as cover_version_id
     from events e
     left join lateral (
       select f.id, f.current_version_id from flyers f
       where f.event_id = e.id and not f.archived and f.current_version_id is not null
       order by f.updated_at desc limit 1
     ) c on true
     order by e.date, e.created_at`,
  );
  return rows.map(mapEvent);
}

export async function listSchedule(eventId: string): Promise<ScheduleItem[]> {
  const rows = await sql("select * from event_schedule where event_id = $1 order by sort", [eventId]);
  return rows.map(mapSchedule);
}

export async function replaceSchedule(eventId: string, items: Omit<ScheduleItem, "id">[]): Promise<ScheduleItem[]> {
  const sorted = items.map((it, i) => ({ ...it, i })).sort((a, b) => sortTime(a.time) - sortTime(b.time) || a.i - b.i);
  await sql("delete from event_schedule where event_id = $1", [eventId]);
  for (const [sort, it] of sorted.entries()) {
    await sql("insert into event_schedule (id, event_id, time, label, kind, notes, sort) values ($1, $2, $3, $4, $5, $6, $7)", [
      newId("slot"),
      eventId,
      it.time,
      it.label,
      it.kind,
      it.notes,
      sort,
    ]);
  }
  await sql("update events set updated_at = now() where id = $1", [eventId]);
  return listSchedule(eventId);
}

/** Flyers are always filed under a calendar event; reuse one on the same date and venue. */
export async function findOrCreateEvent(fields: EventFields): Promise<CalendarEvent> {
  const parsed = EventFieldsSchema.parse(fields);
  const rows = await sql("select * from events where date = $1 and lower(venue) = lower($2) order by created_at limit 1", [parsed.date, parsed.venue]);
  if (rows[0]) return mapEvent(rows[0]);
  return insertEvent(parsed);
}

export const SETLIST_SELECT = `select s.*, e.date as event_date, e.venue as event_venue, e.title as event_title
  from setlists s left join events e on e.id = s.event_id`;
