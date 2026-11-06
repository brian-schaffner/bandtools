"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Asset, Band, Member, StyleRef } from "@/lib/types";

export function useFetch<T>(url: string | null) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(url));
  const [nonce, setNonce] = useState(0);
  const [fetchedUrl, setFetchedUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    api<T>(url)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setError(null);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Something went wrong"))
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
        setFetchedUrl(url);
      });
    return () => {
      cancelled = true;
    };
  }, [url, nonce]);

  const reload = useCallback(() => {
    setLoading(true);
    setNonce((n) => n + 1);
  }, []);

  return { data, setData, error, loading: loading || (url !== null && fetchedUrl !== url), reload };
}

export function useBand() {
  return useFetch<{ band: Band; members: Member[] }>("/api/band");
}

export function useAssets(kind: "logo" | "photo" | "reference") {
  return useFetch<Asset[]>(`/api/assets?kind=${kind}`);
}

export function useRefs() {
  return useFetch<StyleRef[]>("/api/references");
}

let aiStatus: Promise<{ enabled: boolean; model: string }> | null = null;
export function useAiStatus() {
  const [status, setStatus] = useState<{ enabled: boolean; model: string } | null>(null);
  useEffect(() => {
    aiStatus ??= api<{ enabled: boolean; model: string }>("/api/ai/status").catch(() => ({ enabled: false, model: "" }));
    void aiStatus.then(setStatus);
  }, []);
  return status;
}
