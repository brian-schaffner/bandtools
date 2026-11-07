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
  }
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
  const key = [l.assetId, p.sx, p.sy, p.sw, p.sh, ow, oh, t.mode, resolveColor(t.dark, pal), resolveColor(t.light, pal), t.contrast, t.brightness, t.threshold].join("|");
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
    if (t.mode === "threshold") L = L > t.threshold ? 1 : 0;
    else if (t.mode === "tint") L = Math.pow(L, 0.8);
    d[i] = dr + (lr - dr) * L;
    d[i + 1] = dg + (lg - dg) * L;
    d[i + 2] = db + (lb - db) * L;
  }
  cx.putImageData(data, 0, 0);
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

function drawText(ctx: CanvasRenderingContext2D, l: TextLayer, box: Box, pal: Palette, W: number, H: number, report: RenderReport) {
  const text = applyCase(l.text, l.transform);
  const requested = l.size * W;
  let px = requested;
  let lines: string[];
  if (l.fill) {
    lines = text.split("\n");
    setFont(ctx, l, 100);
    const widest = Math.max(...lines.map((s) => ctx.measureText(s).width), 1);
    px = Math.min((100 * box.w) / widest, box.h / (lines.length * l.leading));
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

  const lineH = px * l.leading;
  const cap = ctx.measureText("H").actualBoundingBoxAscent || px * 0.7;
  const total = lines.length * lineH;
  let top = box.y;
  if (l.valign === "middle") top = box.y + (box.h - total) / 2;
  else if (l.valign === "bottom") top = box.y + box.h - total;
  ctx.textBaseline = "alphabetic";
  ctx.textAlign = l.align;
  const ax = l.align === "left" ? box.x : l.align === "right" ? box.x + box.w : box.x + box.w / 2;

  const paint = (color: string, ox: number, oy: number) => {
    ctx.fillStyle = color;
    lines.forEach((s, i) => {
      const baseline = top + i * lineH + lineH / 2 + cap / 2;
      ctx.fillText(s, ax + ox, baseline + oy);
    });
  };
  if (l.misregister) {
    const prev = ctx.globalCompositeOperation;
    ctx.globalCompositeOperation = "multiply";
    paint(resolveColor(l.misregister.color, pal), l.misregister.dx * W, l.misregister.dy * H);
    ctx.globalCompositeOperation = prev;
  }
  paint(resolveColor(l.color, pal), 0, 0);
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
  ctx.globalCompositeOperation = "multiply";
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
