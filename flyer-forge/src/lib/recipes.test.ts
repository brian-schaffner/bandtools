import { test } from "node:test";
import assert from "node:assert/strict";
import { RECIPES, RECIPE_MAP, buildSpec, usefulHeadline } from "./recipes.ts";
import { BriefSchema, FORMATS, resolveColor, type FormatId, type Layer, type LogoLayer, type PhotoLayer, type TextLayer } from "./spec.ts";

const BRIEF = { title: "", date: "2026-11-07", venue: "Two Lane", city: "Louisville, KY", time: "8:00 pm", price: "", support: [], headline: "" };

const FULL = BriefSchema.parse({
  headline: "Ernie's Tavern Presents The Lindsey Lane Band",
  date: "2026-11-14",
  venue: "Ernie's Tavern",
  city: "Bloomfield, KY",
  address: "106 Taylorsville Rd, Bloomfield, KY 40008",
  doors: "6:30 pm",
  showTime: "7:00 pm",
  endTime: "11:00 pm",
  price: "$10",
  support: ["The Openers"],
  tickets: "tickets.example.com",
});

const FORMAT_IDS = Object.keys(FORMATS) as FormatId[];
const variantsOf = (id: string) => RECIPE_MAP[id].variants?.map((v) => v.id) ?? [undefined];

function sourceWindow(l: PhotoLayer, iw: number, ih: number, W: number, H: number) {
  const bw = l.w * W;
  const bh = l.h * H;
  const s = Math.max(bw / iw, bh / ih) * l.zoom;
  return { sw: bw / s, sh: bh / s };
}

for (const [iw, ih] of [
  [3000, 2000],
  [1920, 1080],
]) {
  test(`every recipe, variant and format shows the full width of a ${iw}x${ih} line-up`, () => {
    for (const recipe of RECIPES) {
      for (const variant of variantsOf(recipe.id)) {
        for (const format of FORMAT_IDS) {
          const f = FORMATS[format];
          const spec = buildSpec(recipe.id, { brief: BRIEF as never, bandName: "Lindsey Lane Band", format, photo: { id: "p", width: iw, height: ih }, logo: null, seed: 1, variant });
          const photos = spec.layers.filter((l): l is PhotoLayer => l.type === "photo");
          const where = `${recipe.id}/${variant ?? "-"}/${format}`;
          if (recipe.id === "letterpress" && variant === "type") {
            assert.equal(photos.length, 0, `${where} is type only`);
            continue;
          }
          assert.ok(photos.length > 0, `${where} has a photo`);
          for (const l of photos) {
            const { sw } = sourceWindow(l, iw, ih, f.w, f.h);
            assert.ok(sw >= iw * 0.99, `${where} crops the sides (${Math.round((sw / iw) * 100)}% visible)`);
            assert.equal(l.mask === "ellipse" || l.mask === "arch", false, `${where} uses a curved mask on a wide photo`);
            assert.ok(l.y >= -0.0001 && l.y + l.h <= 1.0001, `${where} photo stays on the page`);
          }
        }
      }
    }
  });
}

test("a portrait photo keeps the recipe's own frame", () => {
  const spec = buildSpec("psych", { brief: BRIEF as never, bandName: "B", format: "ig-square", photo: { id: "p", width: 1600, height: 2000 }, logo: null, seed: 1 });
  const photo = spec.layers.find((l): l is PhotoLayer => l.type === "photo")!;
  assert.equal(photo.mask, "ellipse");
});

test("calendar titles that only repeat the venue or band are not used as headlines", () => {
  assert.equal(usefulHeadline("Ernie's Tavern Presents The Lindsey Lane Band", "Lindsey Lane Band", "Ernie's Tavern"), "");
  assert.equal(usefulHeadline("Two Lane Tavern", "Lindsey Lane Band", "Two Lane"), "");
  assert.equal(usefulHeadline("Lindsey Lane Live at the Legion", "Lindsey Lane Band", "American Legion"), "");
  assert.equal(usefulHeadline("Halloween Costume Bash", "Lindsey Lane Band", "Two Lane"), "Halloween Costume Bash");
  for (const recipe of RECIPES) {
    const spec = buildSpec(recipe.id, { brief: FULL, bandName: "Lindsey Lane Band", format: "poster-11x17", photo: { id: "p", width: 3000, height: 2000 }, logo: null, seed: 1 });
    const texts = spec.layers.filter((l): l is TextLayer => l.type === "text").map((l) => l.text);
    assert.ok(!texts.some((t) => /presents/i.test(t)), `${recipe.id} repeats the calendar title`);
  }
});

const overlap = (a: Layer, b: Layer) => a.x < b.x + b.w - 0.002 && b.x < a.x + a.w - 0.002 && a.y < b.y + b.h - 0.002 && b.y < a.y + a.h - 0.002;

test("info text is legible, on the page, and the logo never sits on the photo", () => {
  for (const recipe of RECIPES) {
    for (const variant of variantsOf(recipe.id)) {
      for (const format of FORMAT_IDS) {
        const where = `${recipe.id}/${variant ?? "-"}/${format}`;
        const spec = buildSpec(recipe.id, { brief: FULL, bandName: "Lindsey Lane Band", format, photo: { id: "p", width: 3000, height: 2000 }, logo: { id: "l", width: 1200, height: 700 }, seed: 3, variant });
        for (const l of spec.layers) {
          if (l.type !== "text") continue;
          assert.ok(l.size >= 0.024, `${where} ${l.role} is requested at ${l.size}`);
          assert.ok(l.x >= -0.001 && l.x + l.w <= 1.001 && l.y >= -0.001 && l.y + l.h <= 1.001, `${where} ${l.role} runs off the page`);
          assert.ok(l.h > 0.02, `${where} ${l.role} has no room`);
        }
        const logo = spec.layers.find((l): l is LogoLayer => l.type === "logo");
        const photo = spec.layers.find((l): l is PhotoLayer => l.type === "photo");
        assert.ok(logo, `${where} places the logo`);
        if (photo) assert.ok(!overlap(logo!, photo), `${where} puts the logo over the photo`);
        for (const role of ["date", "venue", "city", "time"]) {
          const present = spec.layers.some((l) => l.type === "text" && (l.role === role || (role === "city" && l.text.includes("Taylorsville"))));
          assert.ok(present, `${where} is missing ${role}`);
        }
      }
    }
  }
});

test("photos are never multiplied into a colour shape", () => {
  for (const recipe of RECIPES) {
    const spec = buildSpec(recipe.id, { brief: FULL, bandName: "B", format: "ig-portrait", photo: { id: "p", width: 3000, height: 2000 }, logo: null, seed: 1 });
    for (const l of spec.layers) if (l.type === "photo") assert.equal(l.blend, "normal", `${recipe.id} blends the photo`);
  }
});

const hexLum = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return (0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
};

test("on a dark palette the logo is recoloured light and photo highlights stay light", () => {
  for (const recipe of RECIPES) {
    recipe.palettes.forEach((palette, i) => {
      const spec = buildSpec(recipe.id, { brief: FULL, bandName: "B", format: "poster-11x17", photo: { id: "p", width: 3000, height: 2000 }, logo: { id: "l", width: 1200, height: 700 }, seed: 1, paletteIndex: i });
      const logo = spec.layers.find((l): l is LogoLayer => l.type === "logo")!;
      const darkPaper = hexLum(palette.paper) < 0.45;
      if (darkPaper && recipe.id !== "ticket") assert.ok(logo.recolor && hexLum(resolveColor(logo.recolor, palette)) > 0.6, `${recipe.id} #${i} leaves a dark logo on dark paper`);
      if (!darkPaper) assert.equal(logo.recolor, null, `${recipe.id} #${i} recolours a logo on light paper`);
      for (const l of spec.layers) {
        if (l.type !== "photo" || l.treatment.mode === "original" || l.treatment.mode === "mono") continue;
        assert.ok(hexLum(resolveColor(l.treatment.light, palette)) > 0.5, `${recipe.id} #${i} maps photo highlights to a dark ink`);
      }
    });
  }
});
