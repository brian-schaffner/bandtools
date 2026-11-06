import type { Brief, FlyerSpec } from "./spec";

export type AssetKind = "logo" | "photo" | "reference";
export type PhotoKind = "group" | "individual" | "live" | "other";

export interface Asset {
  id: string;
  kind: AssetKind;
  name: string;
  photoKind: PhotoKind | null;
  memberIds: string[];
  mime: string;
  width: number;
  height: number;
  byteSize: number;
  sha256: string;
  chunkCount: number;
  complete: boolean;
  credit: string;
  notes: string;
  focalX: number;
  focalY: number;
  isPrimary: boolean;
  archived: boolean;
  createdAt: string;
}

export interface Member {
  id: string;
  name: string;
  role: string;
  sort: number;
}

export interface Band {
  name: string;
  genre: string;
  hometown: string;
}

export interface StyleRef {
  id: string;
  kind: "avoid" | "inspire";
  title: string;
  notes: string;
  traits: string[];
  recipeId: string | null;
  imageAssetId: string | null;
  seeded: boolean;
  archived: boolean;
  updatedAt: string;
}

export interface CritiqueIssue {
  severity: "pass" | "info" | "warn" | "fail";
  area: string;
  note: string;
  fix?: string;
}

export interface Critique {
  source: "checks" | "ai";
  score: number;
  summary: string;
  issues: CritiqueIssue[];
  createdAt: string;
}

export interface FlyerVersion {
  id: string;
  flyerId: string;
  parentId: string | null;
  label: string;
  source: "concept" | "edit" | "evolve" | "manual" | "ai-edit";
  spec: FlyerSpec;
  critique: Critique | null;
  hasThumb: boolean;
  createdAt: string;
}

export interface Flyer {
  id: string;
  title: string;
  brief: Brief;
  currentVersionId: string | null;
  eventId: string | null;
  archived: boolean;
  createdAt: string;
  updatedAt: string;
  format?: string;
}

export interface ConceptDirection {
  recipeId: string;
  title: string;
  rationale: string;
  paletteIndex?: number;
  palette?: { paper: string; ink: string; accent: string; accent2: string };
  fontIndex?: number;
  fonts?: { display: string; text: string };
  treatment?: string;
  mirror?: boolean;
  photoId?: string | null;
  logoId?: string | null;
  avoids?: string[];
}
