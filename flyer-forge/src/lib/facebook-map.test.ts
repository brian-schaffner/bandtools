import { test } from "node:test";
import assert from "node:assert/strict";
import { localDateTime, mapFacebookEvents, placeDetails, venueFromTitle, type FacebookEvent } from "./facebook-map.ts";

const TZ = "America/Kentucky/Louisville";

const ROWS: FacebookEvent[] = [
  {
    id: "1502409618320369",
    name: "Ernie's Tavern Presents The Lindsey Lane Band",
    start_time: "2027-08-21T19:00:00-0400",
    end_time: "2027-08-21T23:00:00-0400",
    ticket_uri: "https://tickets.example/ernies",
    place: { name: "Ernie's Tavern", location: { street: "104 Taylorsville Rd", city: "Bloomfield", state: "KY", zip: "40008" } },
  },
  { id: "2674098246285278", name: "The Shop Presents The Lindsey Lane", start_time: "2026-12-19T20:30:00-0500", place: { name: "133 Christian Church Rd, Brandenburg, KY" } },
  { id: "1643867556695362", name: "Two Lane Tavern", start_time: "2026-11-07T20:00:00-0500", place: { name: "Two Lane" } },
  { id: "999", name: "Cancelled Show at Nowhere Bar", start_time: "2026-11-28T20:00:00-0500", is_canceled: true },
  {
    id: "1618212279679861",
    name: "Lindsey Lane Tuesday Jam",
    start_time: "2026-10-20T19:30:00-0400",
    place: { name: "Stevie Ray's Blues Bar" },
    event_times: [
      { id: "a", start_time: "2026-11-10T19:30:00-0500" },
      { id: "b", start_time: "2026-11-17T19:30:00-0500" },
    ],
  },
];

test("maps venue, address, city, local time and tickets", () => {
  const ernies = mapFacebookEvents(ROWS, TZ).find((g) => g.uid === "facebook:1502409618320369");
  assert.deepEqual(ernies, {
    uid: "facebook:1502409618320369",
    title: "Ernie's Tavern Presents The Lindsey Lane Band",
    date: "2027-08-21",
    status: "confirmed",
    venue: "Ernie's Tavern",
    city: "Bloomfield, KY",
    address: "104 Taylorsville Rd, Bloomfield, KY 40008",
    showTime: "7:00 pm",
    endTime: "11:00 pm",
    tickets: "https://tickets.example/ernies",
    notes: "",
  });
});

test("address-only place becomes the address and the venue comes from the title", () => {
  assert.deepEqual(placeDetails("The Shop Presents The Lindsey Lane", { name: "133 Christian Church Rd, Brandenburg, KY" }), {
    venue: "The Shop",
    address: "133 Christian Church Rd, Brandenburg, KY",
    city: "",
  });
});

test("recurring events expand per date, cancelled ones are kept as cancelled, sorted by date", () => {
  const gigs = mapFacebookEvents(ROWS, TZ);
  assert.deepEqual(
    gigs.map((g) => [g.date, g.uid, g.status]),
    [
      ["2026-11-07", "facebook:1643867556695362", "confirmed"],
      ["2026-11-10", "facebook:1618212279679861:a", "confirmed"],
      ["2026-11-17", "facebook:1618212279679861:b", "confirmed"],
      ["2026-11-28", "facebook:999", "cancelled"],
      ["2026-12-19", "facebook:2674098246285278", "confirmed"],
      ["2027-08-21", "facebook:1502409618320369", "confirmed"],
    ],
  );
});

test("title equal to venue is dropped so the gig shows the venue name", () => {
  const g = mapFacebookEvents([{ id: "1", name: "Two Lane", start_time: "2026-11-07T20:00:00-0500", place: { name: "Two Lane" } }], TZ)[0];
  assert.equal(g.title, "");
});

test("timestamps convert to the band's time zone", () => {
  assert.deepEqual(localDateTime("2026-11-21T04:30:00+0000", TZ), { date: "2026-11-20", time: "11:30 pm" });
  assert.deepEqual(localDateTime("2026-12-06T13:00:00-0500", TZ), { date: "2026-12-06", time: "1:00 pm" });
  assert.deepEqual(localDateTime("2027-01-01T00:15:00-0500", TZ), { date: "2027-01-01", time: "12:15 am" });
  assert.deepEqual(localDateTime("2027-03-05", TZ), { date: "2027-03-05", time: "" });
  assert.equal(localDateTime("not a date", TZ), null);
});

test("venueFromTitle handles 'at' and 'Hosting' titles", () => {
  assert.equal(venueFromTitle("Holiday Music at Clifton Oaks Care Center"), "Clifton Oaks Care Center");
  assert.equal(venueFromTitle("Hosting Lindsey Lane Band at VFW Post 1170"), "VFW Post 1170");
});
