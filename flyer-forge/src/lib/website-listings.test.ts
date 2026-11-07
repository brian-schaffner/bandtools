import { test } from "node:test";
import assert from "node:assert/strict";
import { cityFromAddress, extractAddress, matchListing, parseWebsiteListings } from "./website-listings.ts";

const article = (date: string, start: string, title: string, end = "") =>
  `<article class="mec-event-article mec-clear" itemscope><div class="mec-event-date mec-color"><span class="mec-start-date-label">${date}</span></div>` +
  `<div class="mec-event-time mec-color"><div class="mec-time-details"><span class="mec-start-time">${start}</span>${end ? `<span class="mec-end-time">${end}</span>` : ""}</div></div>` +
  `<h4 class="mec-event-title"><a class="mec-color-hover" href="https://example.com/e/">${title}</a></h4></article>`;

const HTML = [
  article("Nov 07 2026", "8:00 pm", "Two Lane Tavern 9702 Old Bardstown Rd, Louisville, KY 40291"),
  article("Nov 10 2026", "7:30 pm", "Hosting Stevie Ray&#8217;s World Famous Tuesday Jam"),
  article("Nov 14 2026", "7:00 pm", "Ernie&#8217;s 104 Taylorsville Rd, Bloomfield, KY 40008", "11:00 pm"),
  article("Nov 21 2026", "7:00 pm", "American Legion Post 28 Bonnie Sloan 1930 McDonald Ln, New Albany, IN 47150"),
].join("\n");

test("parses the band website's listings with addresses and end times", () => {
  const rows = parseWebsiteListings(HTML);
  assert.equal(rows.length, 4);
  assert.deepEqual(rows[0], {
    date: "2026-11-07",
    title: "Two Lane Tavern 9702 Old Bardstown Rd, Louisville, KY 40291",
    start: "8:00 pm",
    end: "",
    address: "9702 Old Bardstown Rd, Louisville, KY 40291",
    city: "Louisville, KY",
  });
  assert.equal(rows[1].title, "Hosting Stevie Ray’s World Famous Tuesday Jam");
  assert.equal(rows[1].address, "");
  assert.equal(rows[2].end, "11:00 pm");
});

test("takes the last street number before the first comma", () => {
  assert.equal(extractAddress("American Legion Post 28 Bonnie Sloan 1930 McDonald Ln, New Albany, IN 47150"), "1930 McDonald Ln, New Albany, IN 47150");
  assert.equal(extractAddress("J-Town Eagles"), "");
  assert.equal(cityFromAddress("104 Taylorsville Rd, Bloomfield, KY 40008"), "Bloomfield, KY");
  assert.equal(cityFromAddress("Somewhere"), "");
});

test("matches Facebook gigs to listings by date and venue words", () => {
  const rows = parseWebsiteListings(HTML);
  assert.equal(matchListing({ date: "2026-11-07", venue: "Two Lane", title: "Two Lane Tavern" }, rows)?.address, "9702 Old Bardstown Rd, Louisville, KY 40291");
  assert.equal(matchListing({ date: "2026-11-14", venue: "Ernie's Tavern", title: "Ernie's Tavern Presents The Lindsey Lane Band" }, rows)?.city, "Bloomfield, KY");
  assert.equal(matchListing({ date: "2026-11-14", venue: "The Alibi Bar", title: "" }, rows), null);
  assert.equal(matchListing({ date: "2026-12-01", venue: "Two Lane", title: "" }, rows), null);
});
