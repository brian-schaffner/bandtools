"use client";

import { jsPDF } from "jspdf";
import { FORMATS, type FlyerSpec } from "../spec";
import { fontsFor } from "./checks";
import { canvasSize, renderFlyer, type RenderReport, type SourceImage } from "./render";

export class FidelityError extends Error {}

function assertFidelity(report: RenderReport) {
  const bad = report.fidelity.filter((f) => !f.uniform);
  if (bad.length) throw new FidelityError("Export blocked: an asset would be stretched.");
  if (report.missingAssets.length) throw new FidelityError("Export blocked: an asset could not be loaded.");
}

export async function renderToCanvas(spec: FlyerSpec, images: Map<string, SourceImage>, width: number, bleedPx = 0) {
  await fontsFor(spec);
  const { width: W, height: H } = canvasSize(spec, width);
  const c = document.createElement("canvas");
  c.width = W + 2 * bleedPx;
  c.height = H + 2 * bleedPx;
  const report = renderFlyer(c.getContext("2d")!, spec, images, { width, bleedPx });
  return { canvas: c, report };
}

function toBlob(c: HTMLCanvasElement, type: string, q?: number) {
  return new Promise<Blob>((resolve, reject) => c.toBlob((b) => (b ? resolve(b) : reject(new Error("Export failed"))), type, q));
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export async function exportPng(spec: FlyerSpec, images: Map<string, SourceImage>, filename: string) {
  const f = FORMATS[spec.format];
  const width = f.print ? f.print.w * 300 : f.w;
  const { canvas, report } = await renderToCanvas(spec, images, width);
  assertFidelity(report);
  download(await toBlob(canvas, "image/png"), `${filename}.png`);
}

/** Print PDF at 300 dpi with 1/8" bleed and crop marks. */
export async function exportPrintPdf(spec: FlyerSpec, images: Map<string, SourceImage>, filename: string) {
  const f = FORMATS[spec.format];
  const dpi = 300;
  const trimW = f.print ? f.print.w : f.w / 100;
  const trimH = f.print ? f.print.h : f.h / 100;
  const bleedIn = 0.125;
  const markIn = 0.25;
  const width = Math.round(trimW * dpi);
  const bleedPx = Math.round(bleedIn * dpi);
  const { canvas, report } = await renderToCanvas(spec, images, width, bleedPx);
  assertFidelity(report);
  const pageW = trimW + 2 * (bleedIn + markIn);
  const pageH = trimH + 2 * (bleedIn + markIn);
  const pdf = new jsPDF({ unit: "in", format: [pageW, pageH], orientation: pageW > pageH ? "landscape" : "portrait" });
  const data = canvas.toDataURL("image/jpeg", 0.95);
  pdf.addImage(data, "JPEG", markIn, markIn, trimW + 2 * bleedIn, trimH + 2 * bleedIn);
  pdf.setLineWidth(0.005);
  pdf.setDrawColor(0);
  const x0 = markIn + bleedIn;
  const y0 = markIn + bleedIn;
  const x1 = x0 + trimW;
  const y1 = y0 + trimH;
  const len = markIn - 0.05;
  for (const [x, y, dx, dy] of [
    [x0, y0, -1, -1],
    [x1, y0, 1, -1],
    [x0, y1, -1, 1],
    [x1, y1, 1, 1],
  ] as const) {
    pdf.line(x, y + dy * bleedIn, x, y + dy * (bleedIn + len));
    pdf.line(x + dx * bleedIn, y, x + dx * (bleedIn + len), y);
  }
  download(pdf.output("blob"), `${filename}-print.pdf`);
}

export async function thumbnailBlob(spec: FlyerSpec, images: Map<string, SourceImage>) {
  const { canvas } = await renderToCanvas(spec, images, 360);
  return toBlob(canvas, "image/jpeg", 0.82);
}

export async function critiqueImage(spec: FlyerSpec, images: Map<string, SourceImage>) {
  const { canvas } = await renderToCanvas(spec, images, 1000);
  return canvas.toDataURL("image/jpeg", 0.85);
}
