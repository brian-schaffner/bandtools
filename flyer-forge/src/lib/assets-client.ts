"use client";

import type { Asset } from "./types";

export const CHUNK_SIZE = 3 * 1024 * 1024;

export interface LoadedAsset {
  image: HTMLImageElement;
  /** True when the reassembled bytes hash to the SHA-256 recorded at upload. */
  verified: boolean;
}

const cache = new Map<string, Promise<LoadedAsset>>();

export function loadAsset(asset: Pick<Asset, "id" | "mime" | "chunkCount" | "sha256">): Promise<LoadedAsset> {
  let p = cache.get(asset.id);
  if (!p) {
    p = fetchAsset(asset).catch((e) => {
      cache.delete(asset.id);
      throw e;
    });
    cache.set(asset.id, p);
  }
  return p;
}

async function fetchAsset(asset: Pick<Asset, "id" | "mime" | "chunkCount" | "sha256">): Promise<LoadedAsset> {
  const parts = await Promise.all(
    Array.from({ length: asset.chunkCount }, async (_, i) => {
      const res = await fetch(`/api/assets/${asset.id}/chunks/${i}`);
      if (!res.ok) throw new Error(`Could not load part ${i + 1} of the original`);
      return res.arrayBuffer();
    }),
  );
  const blob = new Blob(parts, { type: asset.mime });
  const hash = await sha256Hex(await blob.arrayBuffer());
  const verified = hash === asset.sha256;
  const renderBlob = asset.mime === "image/svg+xml" ? await svgWithIntrinsicSize(blob) : blob;
  const image = await blobToImage(renderBlob);
  return { image, verified };
}

export async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function blobToImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("The browser could not decode this image"));
    };
    img.src = url;
  });
}

/**
 * Browsers report 0×0 for SVGs without width/height, which breaks canvas drawing.
 * This adds them from the viewBox on an in-memory copy; the stored original is untouched.
 */
export async function svgWithIntrinsicSize(blob: Blob): Promise<Blob> {
  const text = await blob.text();
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  const svg = doc.documentElement;
  if (svg.nodeName.toLowerCase() !== "svg") return blob;
  const vb = svg.getAttribute("viewBox")?.split(/[\s,]+/).map(Number);
  const hasW = /^\d/.test(svg.getAttribute("width") ?? "") && !svg.getAttribute("width")!.endsWith("%");
  const hasH = /^\d/.test(svg.getAttribute("height") ?? "") && !svg.getAttribute("height")!.endsWith("%");
  if (hasW && hasH) return blob;
  const w = vb && vb.length === 4 ? vb[2] : 1000;
  const h = vb && vb.length === 4 ? vb[3] : 1000;
  // Scale up so rasterisation at poster sizes stays sharp; aspect ratio is preserved exactly.
  const k = Math.max(1, 2400 / Math.max(w, h));
  svg.setAttribute("width", String(w * k));
  svg.setAttribute("height", String(h * k));
  if (!vb) svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  return new Blob([new XMLSerializer().serializeToString(doc)], { type: "image/svg+xml" });
}

export async function readImageMeta(file: File): Promise<{ width: number; height: number; image: HTMLImageElement }> {
  const blob = file.type === "image/svg+xml" ? await svgWithIntrinsicSize(file) : file;
  const image = await blobToImage(blob);
  return { width: image.naturalWidth, height: image.naturalHeight, image };
}

export async function makePreview(image: HTMLImageElement, max = 640, keepAlpha = false): Promise<Blob> {
  const s = Math.min(1, max / Math.max(image.naturalWidth, image.naturalHeight));
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(image.naturalWidth * s));
  c.height = Math.max(1, Math.round(image.naturalHeight * s));
  const cx = c.getContext("2d")!;
  cx.imageSmoothingQuality = "high";
  cx.drawImage(image, 0, 0, c.width, c.height);
  return new Promise((resolve, reject) =>
    c.toBlob((b) => (b ? resolve(b) : reject(new Error("Preview failed"))), keepAlpha ? "image/png" : "image/jpeg", 0.85),
  );
}

export async function uploadAsset(
  file: File,
  meta: { kind: Asset["kind"]; name: string; photoKind?: string | null; memberIds?: string[]; credit?: string },
  onProgress?: (fraction: number) => void,
): Promise<Asset> {
  const { width, height, image } = await readImageMeta(file);
  const bytes = await file.arrayBuffer();
  const sha256 = await sha256Hex(bytes);
  const chunkCount = Math.max(1, Math.ceil(bytes.byteLength / CHUNK_SIZE));
  const preview = await makePreview(image, 640, meta.kind === "logo");
  const form = new FormData();
  form.set(
    "meta",
    JSON.stringify({ ...meta, mime: file.type || "application/octet-stream", width, height, byteSize: bytes.byteLength, sha256, chunkCount }),
  );
  form.set("preview", preview);
  const created = await fetch("/api/assets", { method: "POST", body: form });
  if (!created.ok) throw new Error((await created.json().catch(() => null))?.error ?? "Upload failed");
  const asset: Asset = await created.json();
  for (let i = 0; i < chunkCount; i++) {
    const part = bytes.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
    const res = await fetch(`/api/assets/${asset.id}/chunks/${i}`, { method: "PUT", body: part });
    if (!res.ok) throw new Error(`Upload failed on part ${i + 1} of ${chunkCount}`);
    onProgress?.((i + 1) / chunkCount);
  }
  const done = await fetch(`/api/assets/${asset.id}/complete`, { method: "POST" });
  if (!done.ok) throw new Error((await done.json().catch(() => null))?.error ?? "Could not finalise upload");
  return done.json();
}

export const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "image/svg+xml"];
