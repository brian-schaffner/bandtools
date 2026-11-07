import { FORMATS, resolveColor } from "../spec";
import type { FlyerSpec, Layer, LogoLayer, Palette, PhotoLayer, ShapeLayer, TextLayer, Texture, Treatment } from "../spec";
import { nearestWeight } from "../fonts";
import { mulberry32 } from "../recipes";

export type SourceImage = HTMLImageElement | HTMLCanvasElement | ImageBitmap;

export interface RenderOptions {
  /** Output width in device pixels (trim size, excluding bleed). */
  width: number;
  wireframe?: boolean;
  skipTypes?: Layer["type"][];
  bleedPx?: number;
}

export interface FidelityEntry {
  layerId: string;
  assetId: string;
  kind: "photo" | "logo";
  scaleX: number;
  scaleY: number;
  uniform: boolean;
  /** Fraction of the original visible after crop (1 = whole image). */
  visibleFraction: number;
  /** Effective output pixels per source pixel; below ~0.9 the photo is being upsampled. */
  resolution: number;
}

export interface TextReport {
  layerId: string;
  role: TextLayer["role"];
  requestedPx: number;
  finalPx: number;
  box: { x: number; y: number; w: number; h: number };
  color: string;
}

export interface RenderReport {
  width: number;
  height: number;
  fidelity: FidelityEntry[];
  missingAssets: string[];
  text: TextReport[];
}

export function canvasSize(spec: Pick<FlyerSpec, "format">, width: number) {
  const f = FORMATS[spec.format];
  return { width: Math.round(width), height: Math.round((width * f.h) / f.w) };
}

export function renderFlyer(
  ctx: CanvasRenderingContext2D,
  spec: FlyerSpec,
  images: Map<string, SourceImage>,
  opts: RenderOptions,
): RenderReport {
  const { width: W, height: H } = canvasSize(spec, opts.width);
  const b = opts.bleedPx ?? 0;
  const pal = spec.palette;
  const report: RenderReport = { width: W, height: H, fidelity: [], missingAssets: [], text: [] };

  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = resolveColor(spec.background.color, pal);
  ctx.fillRect(0, 0, W + 2 * b, H + 2 * b);
  ctx.translate(b, b);

  for (const layer of spec.layers) {
    if (layer.hidden) continue;
    if (opts.skipTypes?.includes(layer.type)) continue;
    const box = toPx(layer, W, H, b);
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    ctx.globalCompositeOperation = blendOp(layer.blend);
    if (layer.rotation) {
      ctx.translate(box.x + box.w / 2, box.y + box.h / 2);
      ctx.rotate((layer.rotation * Math.PI) / 180);
      ctx.translate(-(box.x + box.w / 2), -(box.y + box.h / 2));
    }
    switch (layer.type) {
      case "shape":
        drawShape(ctx, layer, box, pal);
        break;
      case "photo":
        drawPhoto(ctx, layer, box, pal, images, W, H, opts, report);
        break;
      case "logo":
        drawLogo(ctx, layer, box, pal, images, opts, report);
        break;
      case "text":
        drawText(ctx, layer, box, pal, W, H, report);
        break;
    }
    ctx.restore();
  }

  if (!opts.skipTypes?.includes("shape")) {
    for (const t of spec.background.textures) drawTexture(ctx, t, pal, W, H, b, spec.seed);
  }
  ctx.restore();
  return report;
}

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

function toPx(l: Layer, W: number, H: number, bleed: number): Box {
  let x = l.x * W;
  let y = l.y * H;
  let w = l.w * W;
  let h = l.h * H;
  // Shapes and photos that touch the trim edge extend into the bleed.
  if (bleed > 0 && (l.type === "shape" || l.type === "photo") && !l.rotation) {
    const eps = 0.002;
    if (l.x <= eps) {
      x -= bleed;
      w += bleed;
    }
    if (l.y <= eps) {
      y -= bleed;
      h += bleed;
    }
    if (l.x + l.w >= 1 - eps) w += bleed;
    if (l.y + l.h >= 1 - eps) h += bleed;
  }
  return { x, y, w, h };
}

function blendOp(b: Layer["blend"]): GlobalCompositeOperation {
  return b === "multiply" ? "multiply" : b === "screen" ? "screen" : "source-over";
}

// ---------- shapes ----------

function drawShape(ctx: CanvasRenderingContext2D, l: ShapeLayer, box: Box, pal: Palette) {
  ctx.fillStyle = resolveColor(l.fill, pal);
  ctx.strokeStyle = ctx.fillStyle;
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  switch (l.shape) {
    case "rect":
      ctx.fillRect(box.x, box.y, box.w, box.h);
      break;
    case "ellipse":
      ctx.beginPath();
      ctx.ellipse(cx, cy, box.w / 2, box.h / 2, 0, 0, Math.PI * 2);
      ctx.fill();
      break;
    case "ring":
      ctx.lineWidth = Math.min(box.w, box.h) * 0.04;
      ctx.beginPath();
      ctx.ellipse(cx, cy, box.w / 2 - ctx.lineWidth / 2, box.h / 2 - ctx.lineWidth / 2, 0, 0, Math.PI * 2);
      ctx.stroke();
      break;
    case "sunburst": {
      const r = Math.hypot(box.w, box.h) / 2;
      const n = l.rays;
      const step = (Math.PI * 2) / n;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const a = i * step;
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
        ctx.lineTo(cx + Math.cos(a + step / 2) * r, cy + Math.sin(a + step / 2) * r);
        ctx.closePath();
      }
      ctx.fill();
      break;
    }
    case "stripes": {
      const n = Math.max(2, l.rays);
      const sh = box.h / (n * 2 - 1);
      for (let i = 0; i < n; i++) ctx.fillRect(box.x, box.y + i * 2 * sh, box.w, sh);
      break;
    }
    case "star":
      starPath(ctx, cx, cy, box.w / 2, box.h / 2, 5, 0.42);
      ctx.fill();
      break;
    case "burst":
      starPath(ctx, cx, cy, box.w / 2, box.h / 2, Math.max(8, l.rays), 0.8);
      ctx.fill();
      break;
    case "ribbon": {
      const notch = Math.min(box.h * 0.45, box.w * 0.12);
      ctx.beginPath();
      ctx.moveTo(box.x, box.y);
      ctx.lineTo(box.x + box.w, box.y);
      ctx.lineTo(box.x + box.w - notch, box.y + box.h / 2);
      ctx.lineTo(box.x + box.w, box.y + box.h);
      ctx.lineTo(box.x, box.y + box.h);
      ctx.lineTo(box.x + notch, box.y + box.h / 2);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case "frame": {
      const lw = Math.max(1.5, Math.min(box.w, box.h) * 0.011);
      ctx.lineWidth = lw;
      ctx.strokeRect(box.x + lw / 2, box.y + lw / 2, box.w - lw, box.h - lw);
      if (l.rays >= 2) {
        const inner = lw * 0.4;
        const gap = lw * 1.6;
        ctx.lineWidth = inner;
        ctx.strokeRect(box.x + lw + gap, box.y + lw + gap, box.w - 2 * (lw + gap), box.h - 2 * (lw + gap));
      }
      break;
    }
  }
}

/** A star whose points alternate between the box's edge and `inner` of it. */
function starPath(ctx: CanvasRenderingContext2D, cx: number, cy: number, rx: number, ry: number, points: number, inner: number) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const a = -Math.PI / 2 + (i * Math.PI) / points;
    const k = i % 2 ? inner : 1;
    const x = cx + Math.cos(a) * rx * k;
    const y = cy + Math.sin(a) * ry * k;
    if (i) ctx.lineTo(x, y);
    else ctx.moveTo(x, y);
  }
  ctx.closePath();
}

// ---------- photos ----------

function maskPath(ctx: CanvasRenderingContext2D, mask: PhotoLayer["mask"], box: Box) {
  ctx.beginPath();
  if (mask === "ellipse") {
    ctx.ellipse(box.x + box.w / 2, box.y + box.h / 2, box.w / 2, box.h / 2, 0, 0, Math.PI * 2);
  } else if (mask === "arch") {
    const r = Math.min(box.w / 2, box.h);
    ctx.moveTo(box.x, box.y + box.h);
    ctx.lineTo(box.x, box.y + r);
    ctx.arc(box.x + box.w / 2, box.y + r, box.w / 2, Math.PI, 0);
    ctx.lineTo(box.x + box.w, box.y + box.h);
    ctx.closePath();
  } else if (mask === "slant") {
    ctx.moveTo(box.x, box.y + box.h * 0.12);
    ctx.lineTo(box.x + box.w, box.y);
    ctx.lineTo(box.x + box.w, box.y + box.h * 0.88);
    ctx.lineTo(box.x, box.y + box.h);
    ctx.closePath();
  } else {
    ctx.rect(box.x, box.y, box.w, box.h);
  }
}

interface Placement {
  sx: number;
  sy: number;
  sw: number;
  sh: number;
  dx: number;
  dy: number;
  dw: number;
  dh: number;
}

/** Uniform-scale placement: the only transform applied to an original is one scale factor plus a crop. */
export function placeImage(
  iw: number,
  ih: number,
  box: Box,
  fit: "cover" | "contain",
  zoom: number,
  focusX: number,
  focusY: number,
  align: "left" | "center" | "right" = "center",
): Placement {
  if (fit === "cover") {
    const s = Math.max(box.w / iw, box.h / ih) * zoom;
    const sw = box.w / s;
    const sh = box.h / s;
    const sx = clamp(focusX * iw - sw / 2, 0, iw - sw);
    const sy = clamp(focusY * ih - sh / 2, 0, ih - sh);
    return { sx, sy, sw, sh, dx: box.x, dy: box.y, dw: box.w, dh: box.h };
  }
  const s = Math.min(box.w / iw, box.h / ih) * zoom;
  const dw = iw * s;
  const dh = ih * s;
  const dx = align === "left" ? box.x : align === "right" ? box.x + box.w - dw : box.x + (box.w - dw) / 2;
  const dy = box.y + (box.h - dh) / 2;
  return { sx: 0, sy: 0, sw: iw, sh: ih, dx, dy, dw, dh };
}

function fidelityOf(p: Placement, iw: number, ih: number) {
  const scaleX = p.dw / p.sw;
  const scaleY = p.dh / p.sh;
  return {
    scaleX,
    scaleY,
    uniform: Math.abs(scaleX / scaleY - 1) < 1e-6,
    visibleFraction: (p.sw * p.sh) / (iw * ih),
    resolution: 1 / scaleX,
  };
}

function imgSize(img: SourceImage) {
  if (img instanceof HTMLImageElement) return { iw: img.naturalWidth, ih: img.naturalHeight };
  return { iw: img.width, ih: img.height };
}

const processedCache = new Map<string, HTMLCanvasElement>();
function cacheGet(key: string, make: () => HTMLCanvasElement) {
  const hit = processedCache.get(key);
  if (hit) {
    processedCache.delete(key);
    processedCache.set(key, hit);
    return hit;
  }
  const v = make();
  processedCache.set(key, v);
  while (processedCache.size > 16) processedCache.delete(processedCache.keys().next().value!);
  return v;
}

function drawPhoto(
  ctx: CanvasRenderingContext2D,
  l: PhotoLayer,
  box: Box,
  pal: Palette,
  images: Map<string, SourceImage>,
  W: number,
  H: number,
  opts: RenderOptions,
  report: RenderReport,
) {
  const img = l.assetId ? images.get(l.assetId) : undefined;
  if (opts.wireframe || !img) {
    if (l.assetId && !img && !opts.wireframe) report.missingAssets.push(l.assetId);
    ctx.save();
    maskPath(ctx, l.mask, box);
    ctx.clip();
    drawPlaceholder(ctx, box, pal, "PHOTO");
    ctx.restore();
    return;
  }
  const { iw, ih } = imgSize(img);
  const p = placeImage(iw, ih, box, l.fit, l.zoom, l.focusX, l.focusY);
  report.fidelity.push({ layerId: l.id, assetId: l.assetId!, kind: "photo", ...fidelityOf(p, iw, ih) });

  const ow = Math.max(1, Math.round(p.dw));
  const oh = Math.max(1, Math.round(p.dh));
  const t = l.treatment;
  const key = [l.assetId, p.sx, p.sy, p.sw, p.sh, ow, oh, t.mode, resolveColor(t.dark, pal), resolveColor(t.light, pal), resolveColor(t.mid ?? "$accent", pal), t.contrast, t.brightness, t.threshold].join("|");
  const processed = cacheGet(key, () => {
    const c = document.createElement("canvas");
    c.width = ow;
    c.height = oh;
    const cx = c.getContext("2d", { willReadFrequently: true })!;
    cx.imageSmoothingQuality = "high";
    cx.drawImage(img, p.sx, p.sy, p.sw, p.sh, 0, 0, ow, oh);
    applyTreatment(cx, ow, oh, t, pal);
    return c;
  });

  const matte = l.cutout ? subjectMatte(img, l.assetId!) : null;
  if (matte) {
    const ms = matte.width / iw;
    const crop = { sx: p.sx * ms, sy: p.sy * ms, sw: p.sw * ms, sh: p.sh * ms };
    const cut = cacheGet(`${key}|cut`, () => {
      const c = document.createElement("canvas");
      c.width = ow;
      c.height = oh;
      const cx = c.getContext("2d")!;
      cx.drawImage(processed, 0, 0);
      cx.globalCompositeOperation = "destination-in";
      cx.imageSmoothingQuality = "high";
      cx.drawImage(matte, crop.sx, crop.sy, crop.sw, crop.sh, 0, 0, ow, oh);
      return c;
    });
    if (l.sticker) {
      const color = resolveColor(l.sticker, pal);
      const edge = cacheGet(`${key}|sticker|${color}`, () => {
        const c = document.createElement("canvas");
        c.width = ow;
        c.height = oh;
        const cx = c.getContext("2d")!;
        cx.drawImage(matte, crop.sx, crop.sy, crop.sw, crop.sh, 0, 0, ow, oh);
        cx.globalCompositeOperation = "source-in";
        cx.fillStyle = color;
        cx.fillRect(0, 0, ow, oh);
        return c;
      });
      const r = Math.max(2, Math.min(p.dw, p.dh) * 0.022);
      for (let i = 0; i < 16; i++) {
        const a = (i / 16) * Math.PI * 2;
        ctx.drawImage(edge, p.dx + Math.cos(a) * r, p.dy + Math.sin(a) * r, p.dw, p.dh);
      }
    }
    ctx.drawImage(cut, p.dx, p.dy, p.dw, p.dh);
    return;
  }

  ctx.save();
  maskPath(ctx, l.mask, box);
  ctx.clip();
  if (l.misregister) {
    const ghost = cacheGet(`${key}|ghost|${resolveColor(l.misregister.color, pal)}`, () =>
      silhouette(processed, resolveColor(l.misregister!.color, pal)),
    );
    const prev = ctx.globalCompositeOperation;
    ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(ghost, p.dx + l.misregister.dx * W, p.dy + l.misregister.dy * H, p.dw, p.dh);
    ctx.globalCompositeOperation = prev;
  }
  ctx.drawImage(processed, p.dx, p.dy, p.dw, p.dh);
  ctx.restore();
}

const matteCache = new Map<string, HTMLCanvasElement | null>();

/**
 * The subject of a photo shot against a plain backdrop, as an alpha matte: the backdrop colour is sampled from the
 * border and flood-filled inwards. Busy backgrounds (a bar, a stage) don't key cleanly, so they return null and the
 * photo is shown whole instead.
 */
export function subjectMatte(img: SourceImage, assetId: string): HTMLCanvasElement | null {
  if (matteCache.has(assetId)) return matteCache.get(assetId)!;
  const { iw, ih } = imgSize(img);
  const s = Math.min(1, 640 / Math.max(iw, ih));
  const w = Math.max(8, Math.round(iw * s));
  const h = Math.max(8, Math.round(ih * s));
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const cx = c.getContext("2d", { willReadFrequently: true })!;
  cx.drawImage(img, 0, 0, w, h);
  const data = cx.getImageData(0, 0, w, h);
  const d = data.data;
  const border: number[] = [];
  for (let x = 0; x < w; x++) border.push(x, (h - 1) * w + x);
  for (let y = 1; y < h - 1; y++) border.push(y * w, y * w + w - 1);
  // People usually run off the bottom edge, so the backdrop is judged from the top and sides only, by the most
  // common colour rather than the mean.
  const sample = border.filter((i) => i < (h - 1) * w);
  const bins = new Map<number, number[]>();
  for (const i of sample) {
    const k = ((d[i * 4] >> 4) << 8) | ((d[i * 4 + 1] >> 4) << 4) | (d[i * 4 + 2] >> 4);
    const b = bins.get(k) ?? [0, 0, 0, 0];
    b[0]++;
    b[1] += d[i * 4];
    b[2] += d[i * 4 + 1];
    b[3] += d[i * 4 + 2];
    bins.set(k, b);
  }
  const top = [...bins.values()].sort((a, b) => b[0] - a[0])[0];
  const br = top[1] / top[0];
  const bg = top[2] / top[0];
  const bb = top[3] / top[0];
  const dist = (i: number) => Math.hypot(d[i * 4] - br, d[i * 4 + 1] - bg, d[i * 4 + 2] - bb);
  const TOL = 48;
  const plain = sample.filter((i) => dist(i) < TOL).length / sample.length;
  let result: HTMLCanvasElement | null = null;
  if (plain > 0.7) {
    const bgMask = new Uint8Array(w * h);
    const stack = border.filter((i) => dist(i) < TOL);
    for (const i of stack) bgMask[i] = 1;
    while (stack.length) {
      const i = stack.pop()!;
      const x = i % w;
      const y = (i - x) / w;
      for (const n of [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, y > 0 ? i - w : -1, y < h - 1 ? i + w : -1]) {
        if (n < 0 || bgMask[n]) continue;
        if (dist(n) < TOL) {
          bgMask[n] = 1;
          stack.push(n);
        }
      }
    }
    let subject = 0;
    for (let i = 0; i < w * h; i++) {
      const keep = !bgMask[i];
      if (keep) subject++;
      d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = 0;
      d[i * 4 + 3] = keep ? 255 : 0;
    }
    // A keyed subject that is nearly all or nearly nothing of the frame means the key failed.
    if (subject > w * h * 0.08 && subject < w * h * 0.92) {
      cx.putImageData(data, 0, 0);
      result = document.createElement("canvas");
      result.width = w;
      result.height = h;
      const rx = result.getContext("2d")!;
      rx.filter = "blur(1px)";
      rx.drawImage(c, 0, 0);
    }
  }
  matteCache.set(assetId, result);
  return result;
}

function drawPlaceholder(ctx: CanvasRenderingContext2D, box: Box, pal: Palette, label: string) {
  const ink = resolveColor("$ink", pal);
  ctx.save();
  ctx.globalAlpha *= 0.18;
  ctx.fillStyle = ink;
  ctx.fillRect(box.x, box.y, box.w, box.h);
  ctx.globalAlpha /= 0.18;
  ctx.globalAlpha *= 0.55;
  ctx.strokeStyle = ink;
  ctx.lineWidth = Math.max(1, Math.min(box.w, box.h) * 0.006);
  ctx.setLineDash([ctx.lineWidth * 4, ctx.lineWidth * 3]);
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.beginPath();
  ctx.moveTo(box.x, box.y);
  ctx.lineTo(box.x + box.w, box.y + box.h);
  ctx.moveTo(box.x + box.w, box.y);
  ctx.lineTo(box.x, box.y + box.h);
  ctx.stroke();
  ctx.setLineDash([]);
  const fs = Math.max(10, Math.min(box.w, box.h) * 0.12);
  ctx.font = `700 ${fs}px "IBM Plex Mono", monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = ink;
  ctx.globalAlpha = 0.85;
  ctx.fillText(label, box.x + box.w / 2, box.y + box.h / 2);
  ctx.restore();
}

function hexToRgb(hex: string): [number, number, number] {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const n = parseInt(h.slice(0, 6), 16);
  if (Number.isNaN(n)) return [0, 0, 0];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Per-pixel colour mapping only; geometry and alpha are never touched. */
function applyTreatment(cx: CanvasRenderingContext2D, w: number, h: number, t: Treatment, pal: Palette) {
  if (t.mode === "original" && t.contrast === 0 && t.brightness === 0) return;
  const data = cx.getImageData(0, 0, w, h);
  const d = data.data;
  const [dr, dg, db] = hexToRgb(resolveColor(t.dark, pal));
  const [lr, lg, lb] = hexToRgb(resolveColor(t.light, pal));
  const [mr, mg, mb] = hexToRgb(resolveColor(t.mid ?? "$accent", pal));
  const k = 1 + t.contrast;
  const br = t.brightness;
  const adj = (v: number) => Math.min(1, Math.max(0, (v - 0.5) * k + 0.5 + br));
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i] / 255;
    const g = d[i + 1] / 255;
    const b = d[i + 2] / 255;
    if (t.mode === "original") {
      d[i] = adj(r) * 255;
      d[i + 1] = adj(g) * 255;
      d[i + 2] = adj(b) * 255;
      continue;
    }
    let L = adj(0.299 * r + 0.587 * g + 0.114 * b);
    if (t.mode === "mono") {
      d[i] = d[i + 1] = d[i + 2] = L * 255;
      continue;
    }
    if (t.mode === "posterize") {
      const [r2, g2, b2] = L < t.threshold - 0.17 ? [dr, dg, db] : L < t.threshold + 0.17 ? [mr, mg, mb] : [lr, lg, lb];
      d[i] = r2;
      d[i + 1] = g2;
      d[i + 2] = b2;
      continue;
    }
    if (t.mode === "threshold") L = L > t.threshold ? 1 : 0;
    else if (t.mode === "tint") L = Math.pow(L, 0.8);
    d[i] = dr + (lr - dr) * L;
    d[i + 1] = dg + (lg - dg) * L;
    d[i + 2] = db + (lb - db) * L;
  }
  cx.putImageData(data, 0, 0);
  if (t.mode === "halftone") halftone(cx, w, h, data, [dr, dg, db], [lr, lg, lb]);
}

/** Re-screens a duotone-mapped image as dots of the dark ink on the light ink, like a newspaper print. */
function halftone(cx: CanvasRenderingContext2D, w: number, h: number, mapped: ImageData, dark: number[], light: number[]) {
  const d = mapped.data;
  const cell = Math.max(3, Math.round(Math.max(w, h) / 110));
  const span = Math.hypot(light[0] - dark[0], light[1] - dark[1], light[2] - dark[2]) || 1;
  cx.fillStyle = `rgb(${light.join(",")})`;
  cx.fillRect(0, 0, w, h);
  cx.fillStyle = `rgb(${dark.join(",")})`;
  for (let y = 0; y < h + cell; y += cell) {
    const shift = (y / cell) % 2 ? cell / 2 : 0;
    for (let x = shift; x < w + cell; x += cell) {
      const sx = Math.min(w - 1, Math.max(0, Math.round(x)));
      const sy = Math.min(h - 1, Math.max(0, Math.round(y)));
      const i = (sy * w + sx) * 4;
      const toward = Math.hypot(d[i] - light[0], d[i + 1] - light[1], d[i + 2] - light[2]) / span;
      const r = (cell / 2) * 1.15 * Math.sqrt(Math.min(1, toward));
      if (r < 0.3) continue;
      cx.beginPath();
      cx.arc(x, y, r, 0, Math.PI * 2);
      cx.fill();
    }
  }
}

/** Same pixels as the input, mapped dark→colour / light→white, for overprint misregistration. */
function silhouette(src: HTMLCanvasElement, color: string): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = src.width;
  c.height = src.height;
  const cx = c.getContext("2d", { willReadFrequently: true })!;
  cx.drawImage(src, 0, 0);
  const data = cx.getImageData(0, 0, c.width, c.height);
  const d = data.data;
  const [r, g, b] = hexToRgb(color);
  for (let i = 0; i < d.length; i += 4) {
    const L = (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255;
    d[i] = r + (255 - r) * L;
    d[i + 1] = g + (255 - g) * L;
    d[i + 2] = b + (255 - b) * L;
  }
  cx.putImageData(data, 0, 0);
  return c;
}

// ---------- logos ----------

function badgeCircle(box: Box, align: LogoLayer["align"]) {
  const r = Math.min(box.w, box.h) / 2;
  const cx = align === "left" ? box.x + r : align === "right" ? box.x + box.w - r : box.x + box.w / 2;
  return { cx, cy: box.y + box.h / 2, r };
}

const whiteBoxCache = new Map<string, boolean>();

/** True when the logo was saved on an opaque near-white box: its whole border is solid and light. */
export function hasWhiteBox(img: SourceImage, assetId: string): boolean {
  const cached = whiteBoxCache.get(assetId);
  if (cached !== undefined) return cached;
  const { iw, ih } = imgSize(img);
  const s = Math.min(1, 256 / Math.max(iw, ih));
  const w = Math.max(2, Math.round(iw * s));
  const h = Math.max(2, Math.round(ih * s));
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const cx = c.getContext("2d", { willReadFrequently: true })!;
  cx.drawImage(img, 0, 0, w, h);
  const d = cx.getImageData(0, 0, w, h).data;
  let total = 0;
  let light = 0;
  const at = (x: number, y: number) => {
    const i = (y * w + x) * 4;
    total++;
    if (d[i + 3] > 250 && Math.min(d[i], d[i + 1], d[i + 2]) > 225) light++;
  };
  for (let x = 0; x < w; x++) {
    at(x, 0);
    at(x, h - 1);
  }
  for (let y = 1; y < h - 1; y++) {
    at(0, y);
    at(w - 1, y);
  }
  const result = light / total > 0.9;
  whiteBoxCache.set(assetId, result);
  return result;
}

/** Colour-to-alpha against white: white becomes transparent, inks keep their exact colour, anti-aliased edges stay smooth. */
export function whiteToAlpha(cx: CanvasRenderingContext2D, w: number, h: number) {
  const data = cx.getImageData(0, 0, w, h);
  const d = data.data;
  for (let i = 0; i < d.length; i += 4) {
    const a = Math.max(255 - d[i], 255 - d[i + 1], 255 - d[i + 2]) / 255;
    if (a === 0) {
      d[i + 3] = 0;
      continue;
    }
    d[i] = 255 - (255 - d[i]) / a;
    d[i + 1] = 255 - (255 - d[i + 1]) / a;
    d[i + 2] = 255 - (255 - d[i + 2]) / a;
    d[i + 3] = Math.round(d[i + 3] * a);
  }
  cx.putImageData(data, 0, 0);
}

function drawLogo(
  ctx: CanvasRenderingContext2D,
  l: LogoLayer,
  box: Box,
  pal: Palette,
  images: Map<string, SourceImage>,
  opts: RenderOptions,
  report: RenderReport,
) {
  const img = l.assetId ? images.get(l.assetId) : undefined;
  if (opts.wireframe || !img) {
    if (l.assetId && !img && !opts.wireframe) report.missingAssets.push(l.assetId);
    drawPlaceholder(ctx, box, pal, "LOGO");
    return;
  }
  const { iw, ih } = imgSize(img);
  const backdrop = l.backdrop ?? "auto";
  // Inside a badge the logo sits in the circle's inscribed square so its corners never poke out.
  const badge = backdrop === "badge" ? badgeCircle(box, l.align) : null;
  const target = badge ? { x: badge.cx - badge.r * 0.68, y: badge.cy - badge.r * 0.68, w: badge.r * 1.36, h: badge.r * 1.36 } : box;
  const p = placeImage(iw, ih, target, "contain", 1, 0.5, 0.5, badge ? "center" : l.align);
  report.fidelity.push({ layerId: l.id, assetId: l.assetId!, kind: "logo", ...fidelityOf(p, iw, ih) });
  if (badge) {
    ctx.beginPath();
    ctx.arc(badge.cx, badge.cy, badge.r, 0, Math.PI * 2);
    ctx.fillStyle = "#FFFFFF";
    ctx.fill();
    ctx.lineWidth = Math.max(2, badge.r * 0.05);
    ctx.strokeStyle = "#0D0D0D";
    ctx.stroke();
  }
  const ow = Math.max(1, Math.round(p.dw));
  const oh = Math.max(1, Math.round(p.dh));
  const knockout = backdrop === "remove" || (backdrop === "auto" && hasWhiteBox(img, l.assetId!));
  if (!l.recolor && !knockout) {
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, p.dx, p.dy, p.dw, p.dh);
    return;
  }
  const color = l.recolor ? resolveColor(l.recolor, pal) : "";
  const key = `logo|${l.assetId}|${ow}|${oh}|${color}|${l.recolorMode}|${knockout}`;
  const c = cacheGet(key, () => {
    const c = document.createElement("canvas");
    c.width = ow;
    c.height = oh;
    const cx = c.getContext("2d", { willReadFrequently: true })!;
    cx.imageSmoothingQuality = "high";
    cx.drawImage(img, 0, 0, ow, oh);
    if (knockout) whiteToAlpha(cx, ow, oh);
    if (l.recolor && l.recolorMode === "solid") {
      cx.globalCompositeOperation = "source-in";
      cx.fillStyle = color;
      cx.fillRect(0, 0, ow, oh);
    } else if (l.recolor) {
      const data = cx.getImageData(0, 0, ow, oh);
      const d = data.data;
      const [r, g, b] = hexToRgb(color);
      for (let i = 0; i < d.length; i += 4) {
        const L = (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255;
        d[i] = r + (255 - r) * L;
        d[i + 1] = g + (255 - g) * L;
        d[i + 2] = b + (255 - b) * L;
      }
      cx.putImageData(data, 0, 0);
    }
    return c;
  });
  ctx.drawImage(c, p.dx, p.dy, p.dw, p.dh);
}

// ---------- text ----------

function applyCase(s: string, t: TextLayer["transform"]) {
  return t === "upper" ? s.toUpperCase() : t === "lower" ? s.toLowerCase() : s;
}

function setFont(ctx: CanvasRenderingContext2D, l: TextLayer, px: number) {
  ctx.font = `${nearestWeight(l.font, l.weight)} ${px}px "${l.font}", "Inter", sans-serif`;
  if ("letterSpacing" in ctx) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${l.tracking * px}px`;
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const out: string[] = [];
  for (const para of text.split("\n")) {
    const words = para.split(/\s+/).filter(Boolean);
    if (!words.length) {
      out.push("");
      continue;
    }
    let line = words[0];
    for (const w of words.slice(1)) {
      const test = `${line} ${w}`;
      if (ctx.measureText(test).width <= maxW) line = test;
      else {
        out.push(line);
        line = w;
      }
    }
    out.push(line);
  }
  return out;
}

interface Glyph {
  s: string;
  x: number;
  y: number;
  rot: number;
}

function drawText(ctx: CanvasRenderingContext2D, l: TextLayer, box: Box, pal: Palette, W: number, H: number, report: RenderReport) {
  const text = applyCase(l.text, l.transform);
  const requested = l.size * W;
  const arc = (l.arc ?? 0) !== 0 && !text.includes("\n") ? l.arc : 0;
  // Outlines and shadows sit outside the letters, so a filled line leaves room for them.
  const fx = (l.outline?.width ?? 0) + (l.inline?.width ?? 0) + Math.max(Math.abs(l.shadow?.dx ?? 0), Math.abs(l.shadow?.dy ?? 0));
  let px = requested;
  let lines: string[];
  let glyphs: Glyph[] = [];
  let align: CanvasTextAlign = l.align;
  if (arc) {
    lines = [text];
    setFont(ctx, l, 100);
    const w100 = Math.max(ctx.measureText(text).width, 1);
    const cap100 = (ctx.measureText("H").actualBoundingBoxAscent || 70) * 1.12;
    const theta = Math.abs(arc) * Math.PI * 0.9;
    const chord = Math.sin(theta / 2) / (theta / 2);
    const sag = (1 - Math.cos(theta / 2)) / theta;
    const pad = 1 + fx * 2;
    px = l.fill
      ? Math.min((100 * box.w) / (w100 * chord * pad), (100 * box.h) / ((cap100 + w100 * sag) * pad))
      : Math.min(px, (100 * box.w) / (w100 * chord * pad), (100 * box.h) / ((cap100 + w100 * sag) * pad));
    setFont(ctx, l, px);
    const tw = (w100 * px) / 100;
    const capPx = (cap100 * px) / 100;
    const R = tw / theta;
    const total = capPx + tw * sag;
    const top = l.valign === "top" ? box.y : l.valign === "bottom" ? box.y + box.h - total : box.y + (box.h - total) / 2;
    const cx = box.x + box.w / 2;
    const up = arc > 0;
    const midBaseline = up ? top + capPx * 0.9 : top + tw * sag + capPx * 0.9;
    const cy = up ? midBaseline + R : midBaseline - R;
    let a = -theta / 2;
    align = "center";
    for (const ch of Array.from(text)) {
      const cw = ctx.measureText(ch).width;
      const mid = a + cw / 2 / R;
      glyphs.push(up ? { s: ch, x: cx + R * Math.sin(mid), y: cy - R * Math.cos(mid), rot: mid } : { s: ch, x: cx + R * Math.sin(mid), y: cy + R * Math.cos(mid), rot: -mid });
      a += cw / R;
    }
  } else if (l.fill) {
    lines = text.split("\n");
    setFont(ctx, l, 100);
    const widest = Math.max(...lines.map((s) => ctx.measureText(s).width), 1);
    px = Math.min((100 * box.w) / (widest * (1 + fx * 2)), box.h / (lines.length * l.leading + fx * 2));
    setFont(ctx, l, px);
  } else {
    setFont(ctx, l, px);
    lines = wrap(ctx, text, box.w);
    let guard = 0;
    while (guard++ < 80 && px > 4) {
      const tooTall = lines.length * px * l.leading > box.h * 1.02;
      const tooWide = lines.some((s) => ctx.measureText(s).width > box.w * 1.001);
      if (!tooTall && !tooWide) break;
      px *= 0.95;
      setFont(ctx, l, px);
      lines = wrap(ctx, text, box.w);
    }
  }
  report.text.push({ layerId: l.id, role: l.role, requestedPx: l.fill ? px : requested, finalPx: px, box, color: resolveColor(l.color, pal) });

  if (!arc) {
    const lineH = px * l.leading;
    const cap = ctx.measureText("H").actualBoundingBoxAscent || px * 0.7;
    const total = lines.length * lineH;
    let top = box.y;
    if (l.valign === "middle") top = box.y + (box.h - total) / 2;
    else if (l.valign === "bottom") top = box.y + box.h - total;
    const inset = fx * px;
    const ax = l.align === "left" ? box.x + inset : l.align === "right" ? box.x + box.w - inset : box.x + box.w / 2;
    glyphs = lines.map((s, i) => ({ s, x: ax, y: top + i * lineH + lineH / 2 + cap / 2, rot: 0 }));
  }
  ctx.textBaseline = "alphabetic";
  ctx.textAlign = align;
  ctx.lineJoin = "round";
  ctx.miterLimit = 2;

  const run = (op: "fill" | "stroke", color: string, ox: number, oy: number, lineWidth = 0) => {
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    for (const g of glyphs) {
      if (g.rot) {
        ctx.save();
        ctx.translate(g.x + ox, g.y + oy);
        ctx.rotate(g.rot);
        if (op === "fill") ctx.fillText(g.s, 0, 0);
        else ctx.strokeText(g.s, 0, 0);
        ctx.restore();
      } else if (op === "fill") ctx.fillText(g.s, g.x + ox, g.y + oy);
      else ctx.strokeText(g.s, g.x + ox, g.y + oy);
    }
  };
  const ow = (l.outline?.width ?? 0) * px;
  const iw = (l.inline?.width ?? 0) * px;
  const body = (dx: number, dy: number, fill: string, outline: string | null, inline: string | null) => {
    if (outline && inline) {
      run("stroke", outline, dx, dy, 2 * (ow + iw));
      run("stroke", inline, dx, dy, 2 * iw);
    } else if (outline) run("stroke", outline, dx, dy, 2 * ow);
    run("fill", fill, dx, dy);
  };
  if (l.shadow) {
    const sc = resolveColor(l.shadow.color, pal);
    body(l.shadow.dx * px, l.shadow.dy * px, sc, l.outline ? sc : null, l.inline && l.outline ? sc : null);
  }
  if (l.misregister) {
    const prev = ctx.globalCompositeOperation;
    ctx.globalCompositeOperation = "multiply";
    run("fill", resolveColor(l.misregister.color, pal), l.misregister.dx * W, l.misregister.dy * H);
    ctx.globalCompositeOperation = prev;
  }
  body(0, 0, resolveColor(l.color, pal), l.outline ? resolveColor(l.outline.color, pal) : null, l.inline ? resolveColor(l.inline.color, pal) : null);
}

// ---------- textures ----------

const textureCache = new Map<string, HTMLCanvasElement>();

function textureTile(t: Texture, color: string, tile: number, seed: number): HTMLCanvasElement {
  const key = `${t.kind}|${color}|${tile}|${seed}`;
  const hit = textureCache.get(key);
  if (hit) return hit;
  const c = document.createElement("canvas");
  c.width = c.height = tile;
  const cx = c.getContext("2d")!;
  const rng = mulberry32(seed ^ tile);
  const [r, g, b] = hexToRgb(color);
  cx.fillStyle = color;
  cx.strokeStyle = color;
  const unit = tile / 256;
  if (t.kind === "grain") {
    const img = cx.createImageData(tile, tile);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = rng();
      if (v > 0.5) {
        img.data[i] = r;
        img.data[i + 1] = g;
        img.data[i + 2] = b;
        img.data[i + 3] = (v - 0.5) * 2 * 255;
      }
    }
    cx.putImageData(img, 0, 0);
  } else if (t.kind === "speckle") {
    for (let i = 0; i < 90; i++) {
      const s = (0.5 + rng() * (rng() > 0.92 ? 3.5 : 1.2)) * unit;
      cx.globalAlpha = 0.4 + rng() * 0.6;
      cx.beginPath();
      cx.ellipse(rng() * tile, rng() * tile, s, s * (0.6 + rng() * 0.6), rng() * Math.PI, 0, Math.PI * 2);
      cx.fill();
    }
  } else if (t.kind === "paper") {
    cx.lineCap = "round";
    for (let i = 0; i < 160; i++) {
      const x = rng() * tile;
      const y = rng() * tile;
      const a = rng() * Math.PI;
      const len = (4 + rng() * 14) * unit;
      cx.globalAlpha = 0.15 + rng() * 0.35;
      cx.lineWidth = (0.3 + rng() * 0.6) * unit;
      cx.beginPath();
      cx.moveTo(x, y);
      cx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
      cx.stroke();
    }
    const img = cx.getImageData(0, 0, tile, tile);
    for (let i = 0; i < img.data.length; i += 4) {
      if (rng() > 0.7) {
        img.data[i] = r;
        img.data[i + 1] = g;
        img.data[i + 2] = b;
        img.data[i + 3] = Math.max(img.data[i + 3], rng() * 40);
      }
    }
    cx.putImageData(img, 0, 0);
  } else if (t.kind === "halftone") {
    const step = 8 * unit;
    for (let y = 0; y < tile; y += step) {
      for (let x = (y / step) % 2 ? step / 2 : 0; x < tile; x += step) {
        cx.beginPath();
        cx.arc(x, y, step * 0.28, 0, Math.PI * 2);
        cx.fill();
      }
    }
  } else if (t.kind === "distress") {
    // Worn ink: clusters of flecks where the paper shows through, plus a few hairline scratches.
    for (let c = 0; c < 14; c++) {
      const cx0 = rng() * tile;
      const cy0 = rng() * tile;
      const spread = (6 + rng() * 26) * unit;
      for (let i = 0; i < 40; i++) {
        const s = (0.4 + rng() * rng() * 3) * unit;
        cx.globalAlpha = 0.5 + rng() * 0.5;
        cx.beginPath();
        cx.ellipse(cx0 + (rng() - 0.5) * spread * 2, cy0 + (rng() - 0.5) * spread, s, s * (0.4 + rng() * 0.8), rng() * Math.PI, 0, Math.PI * 2);
        cx.fill();
      }
    }
    cx.lineCap = "round";
    for (let i = 0; i < 6; i++) {
      const x = rng() * tile;
      const y = rng() * tile;
      const a = (rng() - 0.5) * 0.6;
      const len = (20 + rng() * 60) * unit;
      cx.globalAlpha = 0.6;
      cx.lineWidth = (0.4 + rng() * 0.6) * unit;
      cx.beginPath();
      cx.moveTo(x, y);
      cx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
      cx.stroke();
    }
  } else if (t.kind === "lines") {
    const step = 6 * unit;
    for (let y = 0; y < tile; y += step) cx.fillRect(0, y, tile, Math.max(1, unit));
  }
  textureCache.set(key, c);
  return c;
}

function drawTexture(ctx: CanvasRenderingContext2D, t: Texture, pal: Palette, W: number, H: number, bleed: number, seed: number) {
  if (t.opacity <= 0) return;
  const color = resolveColor(t.color, pal);
  // Tile size tracks output width so preview and print exports have the same visual grain.
  const tile = Math.max(32, Math.round(256 * (W / 1100) * t.scale));
  const pattern = ctx.createPattern(textureTile(t, color, tile, seed), "repeat");
  if (!pattern) return;
  ctx.save();
  ctx.globalAlpha = t.opacity;
  // Distress knocks ink back to paper, so it paints over rather than darkening.
  ctx.globalCompositeOperation = t.kind === "distress" ? "source-over" : "multiply";
  ctx.fillStyle = pattern;
  ctx.fillRect(-bleed, -bleed, W + 2 * bleed, H + 2 * bleed);
  ctx.restore();
}

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

export function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a: number, b: number) {
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}
