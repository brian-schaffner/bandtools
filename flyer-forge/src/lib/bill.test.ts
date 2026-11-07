import { test } from "node:test";
import assert from "node:assert/strict";
import { buildSpec, RECIPES } from "./recipes.ts";
import { parseBill } from "./bill.ts";
import { BriefSchema, FORMATS, resolveColor, type FormatId, type Layer, type PhotoLayer, type TextLayer } from "./spec.ts";

const BRIEF = BriefSchema.parse({
  headline: "Ernie's Tavern Presents The Lindsey Lane Band",
  date: "2026-11-14",
  venue: "Ernie's Tavern",
  city: "Bloomfield, KY",
  address: "106 Taylorsville Rd, Bloomfield, KY 40008",
  doors: "6:30 pm",
  showTime: "7:00 pm",
  endTime: "11:00 pm",
  support: ["The Openers"],
  songs: ["Sweet Home Alabama", "Midnight Rider"],
});
const BILLS = RECIPES.filter((r) => r.bill);
const PHOTO = { id: "p", width: 3000, height: 2000 };
const texts = (layers: Layer[]) => layers.filter((l): l is TextLayer => l.type === "text");

const lum = (hex: string) => {
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(hex.slice(1 + i, 3 + i), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a: string, b: string) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);

test("there are six built-in bill styles", () => {
  assert.deepEqual(BILLS.map((r) => r.id).sort(), ["ballroom", "handbill", "inperson", "opry", "showcard", "woodtype"]);
});

test("a bill from the model is parsed leniently: bad fields fall back, bad lines are dropped", () => {
  const bill = parseBill({
    paper: "red",
    frame: "triple",
    lines: [{ role: "band", size: 99, font: "Comic Sans", color: "$accent" }, { role: "date", size: 1.2 }, { role: "lyrics" }, "junk"],
  });
  assert.ok(bill);
  assert.equal(bill.paper, "$paper");
  assert.equal(bill.frame, "none");
  assert.equal(bill.lines.length, 2);
  assert.equal(bill.lines[0].size, 1);
  assert.equal(parseBill({ lines: [{ role: "band" }] }), null);
  assert.equal(parseBill("nope"), null);
});

test("a custom bill takes every fact from the brief and skips roles the brief leaves empty", () => {
  const bill = {
    paper: "$paper",
    lines: [
      { role: "custom", text: "Starring", size: 0.5 },
      { role: "band", size: 3, font: "Comic Sans" },
      { role: "price", size: 0.6, text: "$99" },
      { role: "weekday", size: 0.8 },
      { role: "monthday", size: 1.2 },
      { role: "venue", size: 1 },
      { role: "where", size: 0.5 },
      { role: "time", size: 0.5 },
      { role: "songs", size: 0.5 },
    ],
  };
  const spec = buildSpec("bill", { brief: BRIEF, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: null, logo: null, seed: 1, bill });
  const all = texts(spec.layers).map((l) => l.text);
  assert.ok(all.includes("Starring"));
  assert.ok(!all.some((t) => t.includes("$99")), "price is not in the brief, so the line is skipped");
  assert.ok(all.includes("Saturday"));
  assert.ok(all.includes("November 14"));
  assert.ok(all.includes("106 Taylorsville Rd, Bloomfield, KY 40008"));
  assert.ok(all.includes("Doors 6:30 pm · Show 7:00 pm – 11:00 pm"));
  assert.ok(all.some((t) => t.includes("“Sweet Home Alabama”")));
  const band = texts(spec.layers).find((l) => l.role === "band")!;
  assert.notEqual(band.font, "Comic Sans", "unknown fonts fall back to the pairing");
});

test("every bill line reads against what it is printed on", () => {
  for (const recipe of BILLS) {
    recipe.palettes.forEach((palette, i) => {
      for (const seed of [1, 2, 3, 4]) {
        const spec = buildSpec(recipe.id, { brief: BRIEF, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: PHOTO, logo: null, seed, paletteIndex: i });
        spec.layers.forEach((l, k) => {
          if (l.type !== "text") return;
          const cx = l.x + l.w / 2;
          const cy = l.y + l.h / 2;
          const under = spec.layers
            .slice(0, k)
            .filter((s) => s.type === "shape" && (s.shape === "rect" || s.shape === "ribbon") && s.x <= cx && cx <= s.x + s.w && s.y <= cy && cy <= s.y + s.h)
            .pop();
          const ground = resolveColor(under?.type === "shape" ? under.fill : spec.background.color, palette);
          const ink = resolveColor(l.color, palette);
          assert.ok(ratio(ink, ground) >= 2.9, `${recipe.id} #${i} seed ${seed}: ${l.role} "${l.text}" ${ink} on ${ground}`);
        });
      }
    });
  }
});

test("the presenter line never just repeats the venue, but an explicit presenter is used", () => {
  for (const recipe of BILLS) {
    const spec = buildSpec(recipe.id, { brief: BRIEF, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: PHOTO, logo: null, seed: 1 });
    assert.ok(!texts(spec.layers).some((l) => /presents/i.test(l.text)), `${recipe.id} repeats the venue as presenter`);
  }
  const brief = { ...BRIEF, presenter: "WFPK presents" };
  const spec = buildSpec("woodtype", { brief, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: PHOTO, logo: null, seed: 1 });
  assert.ok(texts(spec.layers).some((l) => l.text === "WFPK presents"));
});

test("bill styles are deterministic per seed and vary across seeds", () => {
  for (const recipe of BILLS) {
    const make = (seed: number) => buildSpec(recipe.id, { brief: BRIEF, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: PHOTO, logo: null, seed });
    assert.deepEqual(make(7), make(7), `${recipe.id} is not repeatable`);
    const shapes = new Set([1, 2, 3, 4, 5, 6, 7, 8].map((s) => JSON.stringify(make(s).layers.map((l) => [l.type, l.type === "text" ? l.font : "", Math.round(l.y * 50)]))));
    assert.ok(shapes.size >= 2, `${recipe.id} gives the same layout for every seed`);
  }
});

test("a portrait photo can sit beside the copy without touching any line", () => {
  const portrait = { id: "p", width: 1600, height: 2000 };
  for (const recipe of BILLS) {
    for (const format of Object.keys(FORMATS) as FormatId[]) {
      for (const seed of [1, 2, 3, 4, 5, 6]) {
        const spec = buildSpec(recipe.id, { brief: BRIEF, bandName: "Lindsey Lane Band", format, photo: portrait, logo: null, seed });
        const photo = spec.layers.find((l): l is PhotoLayer => l.type === "photo");
        if (!photo) continue;
        assert.ok(photo.x >= -0.001 && photo.x + photo.w <= 1.001 && photo.y >= -0.001 && photo.y + photo.h <= 1.001, `${recipe.id}/${format}/${seed} photo off the page`);
        if (photo.rotation) continue;
        for (const t of texts(spec.layers)) {
          const hit = t.x < photo.x + photo.w - 0.003 && photo.x < t.x + t.w - 0.003 && t.y < photo.y + photo.h - 0.003 && photo.y < t.y + t.h - 0.003;
          assert.ok(!hit, `${recipe.id}/${format}/${seed}: ${t.role} overlaps the photo`);
        }
      }
    }
  }
});

test("long band names are broken onto two lines when that sets them larger", () => {
  const spec = buildSpec("woodtype", { brief: BRIEF, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: PHOTO, logo: null, seed: 1 });
  const band = texts(spec.layers).find((l) => l.role === "band")!;
  assert.ok(band.text.includes("\n"), band.text);
});
