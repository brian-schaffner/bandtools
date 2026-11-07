import { test } from "node:test";
import assert from "node:assert/strict";
import { RECIPES, buildSpec } from "./recipes.ts";
import { FORMATS, type FormatId, type PhotoLayer } from "./spec.ts";

const BRIEF = { title: "", date: "2026-11-07", venue: "Two Lane", city: "Louisville, KY", time: "8:00 pm", price: "", support: [], headline: "" };

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
  test(`every recipe and format shows the full width of a ${iw}x${ih} line-up`, () => {
    for (const recipe of RECIPES) {
      for (const format of Object.keys(FORMATS) as FormatId[]) {
        const f = FORMATS[format];
        const spec = buildSpec(recipe.id, { brief: BRIEF as never, bandName: "Lindsey Lane Band", format, photo: { id: "p", width: iw, height: ih }, logo: null, seed: 1 });
        const photos = spec.layers.filter((l): l is PhotoLayer => l.type === "photo");
        assert.ok(photos.length > 0, `${recipe.id}/${format} has a photo`);
        for (const l of photos) {
          const { sw } = sourceWindow(l, iw, ih, f.w, f.h);
          assert.ok(sw >= iw * 0.99, `${recipe.id}/${format} crops the sides (${Math.round((sw / iw) * 100)}% visible)`);
          assert.equal(l.mask === "ellipse" || l.mask === "arch", false, `${recipe.id}/${format} uses a curved mask on a wide photo`);
          assert.ok(l.y >= 0 && l.y + l.h <= 1.0001, `${recipe.id}/${format} photo stays on the page`);
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
