import "server-only";
import type { CalendarEvent, EventFields } from "./events";
import { getEvent, replaceSchedule, updateEvent } from "./events-repo";
import { estimateDrive, type DriveEstimate } from "./drive-time";
import { DEFAULT_NO_TRAILER_VENUES, planGig } from "./gig-schedule";
import { getBand } from "./repo";

/** Fill in the drive time from the band's home address, unless it's already known or there's nothing to look up. */
export async function ensureDriveTime(event: CalendarEvent, force = false): Promise<{ event: CalendarEvent; estimate?: DriveEstimate; error?: string }> {
  if (event.driveMinutes != null && !force) return { event };
  const band = await getBand();
  if (!band.homeAddress) return { event, error: "Add the band's home address in Band kit to estimate drive times." };
  if (!event.address && !event.venue && !event.city) return { event, error: "Add the venue's address to estimate the drive." };
  try {
    const estimate = await estimateDrive(band.homeAddress, event);
    const saved = await updateEvent(event.id, { driveMinutes: estimate.minutes } as Partial<EventFields>);
    return { event: saved ?? event, estimate };
  } catch (e) {
    return { event, error: e instanceof Error ? e.message : "Drive time lookup failed" };
  }
}

export async function buildScheduleFromRules(eventId: string) {
  const found = await getEvent(eventId);
  if (!found) return null;
  const { event, estimate, error } = await ensureDriveTime(found);
  const band = await getBand();
  const plan = planGig(event, band.noTrailerVenues ?? DEFAULT_NO_TRAILER_VENUES);
  const items = plan.items.length ? await replaceSchedule(eventId, plan.items) : null;
  return { event, items, plan, estimate: estimate ?? null, problems: error ? [error, ...plan.problems.filter((p) => !p.startsWith("Drive time"))] : plan.problems };
}
