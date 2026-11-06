"use client";

import { useEffect, useRef, useState } from "react";
import { loadAsset } from "@/lib/assets-client";
import type { SourceImage } from "@/lib/render/render";
import type { Asset } from "@/lib/types";

/** Loads full-resolution originals for the given asset ids (cached across the session). */
export function useAssetImages(assets: Asset[] | undefined, ids: (string | null | undefined)[]) {
  const key = [...new Set(ids.filter(Boolean) as string[])].sort().join(",");
  const known = (assets ?? []).filter((a) => key.split(",").includes(a.id));
  const knownKey = known.map((a) => a.id).sort().join(",");
  const assetsRef = useRef(known);
  useEffect(() => {
    assetsRef.current = known;
  });

  const [images, setImages] = useState<Map<string, SourceImage>>(new Map());
  const [verified, setVerified] = useState<Map<string, boolean>>(new Map());
  const [settledKey, setSettledKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const wanted = assetsRef.current.filter((a) => knownKey.split(",").includes(a.id));
    if (!wanted.length) return;
    Promise.all(wanted.map(async (a) => [a.id, await loadAsset(a)] as const))
      .then((entries) => {
        if (cancelled) return;
        setImages((prev) => {
          if (entries.every(([id, l]) => prev.get(id) === l.image)) return prev;
          const next = new Map(prev);
          for (const [id, l] of entries) next.set(id, l.image);
          return next;
        });
        setVerified((prev) => {
          if (entries.every(([id, l]) => prev.get(id) === l.verified)) return prev;
          const next = new Map(prev);
          for (const [id, l] of entries) next.set(id, l.verified);
          return next;
        });
        setError(null);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not load originals"))
      .finally(() => !cancelled && setSettledKey(knownKey));
    return () => {
      cancelled = true;
    };
  }, [knownKey]);

  const loading = knownKey !== "" && settledKey !== knownKey;
  return { images, verified, loading, error };
}
