import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_NO_TRAILER_VENUES, parseClock, planGig, roundDeparture, scheduleText, usesTrailer } from "./gig-schedule.ts";

const at = (t: string) => parseClock(t)!;

test("departure snaps to a quarter hour only within five minutes", () => {
  assert.equal(roundDeparture(at("4:35pm")), at("4:30pm"));
  assert.equal(roundDeparture(at("4:40pm")), at("4:45pm"));
  assert.equal(roundDeparture(at("4:25pm")), at("4:30pm"));
  assert.equal(roundDeparture(at("4:37pm")), at("4:37pm"));
  assert.equal(roundDeparture(at("4:22pm")), at("4:22pm"));
  assert.equal(roundDeparture(at("4:30pm")), at("4:30pm"));
});

test("trailer is assumed except at the no-trailer venues, and a gig can override", () => {
  const list = DEFAULT_NO_TRAILER_VENUES;
  assert.equal(usesTrailer({ venue: "Headliners Music Hall", trailer: "auto" }, list), true);
  assert.equal(usesTrailer({ venue: "Stevie Ray's Blues Bar", trailer: "auto" }, list), false);
  assert.equal(usesTrailer({ venue: "stevie rays", trailer: "auto" }, list), false);
  assert.equal(usesTrailer({ venue: "Stevie Ray's", trailer: "yes" }, list), true);
  assert.equal(usesTrailer({ venue: "Caesars Southern Indiana", trailer: "no" }, list), false);
});

test("the example gig: 8–11 PM show, 45 min drive without the trailer", () => {
  const plan = planGig({ venue: "Stevie Ray's", showTime: "20:00", endTime: "23:00", trailer: "auto", driveMinutes: 45 }, DEFAULT_NO_TRAILER_VENUES);
  assert.deepEqual(plan.problems, []);
  assert.equal(plan.trailer, false);
  assert.equal(plan.travelMinutes, 60);
  assert.deepEqual(
    plan.items.map((i) => [i.time, i.endTime, i.label, i.kind]),
    [
      ["16:30", "", "Depart home", "travel"],
      ["17:30", "", "Arrive at venue", "arrive"],
      ["17:30", "19:30", "Unload, setup & sound check", "load-in"],
      ["19:30", "20:00", "Dead stage", "dead-stage"],
      ["20:00", "23:00", "PERFORMANCE", "set"],
      ["23:00", "", "Teardown & load out", "load-out"],
    ],
  );
  assert.equal(
    scheduleText({ bandName: "Lindsey Lane Band", venue: "Venue Name", date: "2026-11-07" }, plan.items),
    [
      "🎸 LINDSEY LANE BAND\n📍 Venue Name\n📅 Saturday, November 7",
      "🚗 4:30 PM – Depart home",
      "📍 5:30 PM – Arrive at venue",
      "🎤 5:30–7:30 PM – Unload, setup & sound check",
      "🔇 7:30–8:00 PM – Dead stage",
      "🎶 8:00–11:00 PM – PERFORMANCE",
      "📦 11:00 PM – Teardown & load out",
    ].join("\n\n"),
  );
});

test("towing the trailer adds time and an off-quarter departure stays exact", () => {
  const plan = planGig({ venue: "Headliners", showTime: "9pm", endTime: "12:30am", trailer: "auto", driveMinutes: 48 }, DEFAULT_NO_TRAILER_VENUES);
  assert.equal(plan.trailer, true);
  // 48 + 5 towing + 15 cushion = 68 before a 6:30 arrival -> 5:22, more than 5 min from a quarter, kept exact.
  assert.equal(plan.travelMinutes, 68);
  assert.equal(plan.items[0].time, "17:22");
  const boundary = planGig({ venue: "Headliners", showTime: "9pm", endTime: "", trailer: "auto", driveMinutes: 50 }, DEFAULT_NO_TRAILER_VENUES);
  assert.equal(boundary.items[0].time, "17:15");
  assert.equal(plan.items[1].time, "18:30");
  assert.equal(plan.items.at(-1)!.time, "00:30");
  const text = scheduleText({ bandName: "Lindsey Lane Band", venue: "Headliners", date: "2026-12-31" }, plan.items);
  assert.match(text, /🎶 9:00 PM–12:30 AM – PERFORMANCE/);
  assert.match(text, /📦 12:30 AM – Teardown & load out$/);
});

test("an afternoon gig keeps morning times in the morning", () => {
  assert.equal(parseClock("10:45"), 10 * 60 + 45);
  assert.equal(parseClock("8:30"), 20 * 60 + 30);
  const plan = planGig({ venue: "Festival", showTime: "1pm", endTime: "2:30pm", trailer: "auto", driveMinutes: 85 }, []);
  const text = scheduleText({ bandName: "Lindsey Lane Band", venue: "Festival", date: "2026-07-04" }, plan.items);
  assert.match(text, /🚗 8:45 AM – Depart home\n\n📍 10:30 AM – Arrive at venue\n\n🎤 10:30 AM–12:30 PM – Unload/);
});

test("arrival is never rounded and missing facts are reported, not invented", () => {
  const plan = planGig({ venue: "X", showTime: "8:10pm", endTime: "", trailer: "no", driveMinutes: null }, []);
  assert.equal(plan.items[0].label, "Arrive at venue");
  assert.equal(plan.items[0].time, "17:40");
  assert.equal(plan.items.some((i) => i.kind === "load-out"), false);
  assert.equal(plan.problems.length, 2);
  assert.equal(planGig({ venue: "X", showTime: "", endTime: "", trailer: "auto", driveMinutes: 30 }, []).items.length, 0);
});
