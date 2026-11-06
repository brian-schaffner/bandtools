import "server-only";
import { sql } from "./db";
import type { Asset, Band, Flyer, FlyerVersion, Member, StyleRef } from "./types";

type Row = Record<string, unknown>;

const iso = (v: unknown) => (v instanceof Date ? v.toISOString() : String(v));
const json = <T,>(v: unknown, fallback: T): T => {
  if (v == null) return fallback;
  if (typeof v === "string") {
    try {
      return JSON.parse(v) as T;
    } catch {
      return fallback;
    }
  }
  return v as T;
};

export const ASSET_COLS =
  "id, kind, name, photo_kind, member_ids, mime, width, height, byte_size, sha256, chunk_count, complete, credit, notes, focal_x, focal_y, is_primary, archived, created_at";

export function mapAsset(r: Row): Asset {
  return {
    id: String(r.id),
    kind: r.kind as Asset["kind"],
    name: String(r.name ?? ""),
    photoKind: (r.photo_kind as Asset["photoKind"]) ?? null,
    memberIds: json<string[]>(r.member_ids, []),
    mime: String(r.mime),
    width: Number(r.width),
    height: Number(r.height),
    byteSize: Number(r.byte_size),
    sha256: String(r.sha256),
    chunkCount: Number(r.chunk_count),
    complete: Boolean(r.complete),
    credit: String(r.credit ?? ""),
    notes: String(r.notes ?? ""),
    focalX: Number(r.focal_x),
    focalY: Number(r.focal_y),
    isPrimary: Boolean(r.is_primary),
    archived: Boolean(r.archived),
    createdAt: iso(r.created_at),
  };
}

export async function getAsset(id: string): Promise<Asset | null> {
  const rows = await sql(`select ${ASSET_COLS} from assets where id = $1`, [id]);
  return rows[0] ? mapAsset(rows[0]) : null;
}

export async function listAssets(kind?: string): Promise<Asset[]> {
  const rows = kind
    ? await sql(`select ${ASSET_COLS} from assets where kind = $1 and complete order by is_primary desc, created_at desc`, [kind])
    : await sql(`select ${ASSET_COLS} from assets where complete order by is_primary desc, created_at desc`);
  return rows.map(mapAsset);
}

export async function getBand(): Promise<Band> {
  const rows = await sql<{ name: string; genre: string; hometown: string }>("select name, genre, hometown from band where id = 1");
  return rows[0] ?? { name: "", genre: "", hometown: "" };
}

export async function listMembers(): Promise<Member[]> {
  const rows = await sql("select id, name, role, sort from members order by sort, created_at");
  return rows.map((r) => ({ id: String(r.id), name: String(r.name), role: String(r.role ?? ""), sort: Number(r.sort) }));
}

export function mapRef(r: Row): StyleRef {
  return {
    id: String(r.id),
    kind: r.kind as StyleRef["kind"],
    title: String(r.title),
    notes: String(r.notes ?? ""),
    traits: json<string[]>(r.traits, []),
    recipeId: (r.recipe_id as string) ?? null,
    imageAssetId: (r.image_asset_id as string) ?? null,
    seeded: Boolean(r.seeded),
    archived: Boolean(r.archived),
    updatedAt: iso(r.updated_at),
  };
}

export async function listRefs(includeArchived = false): Promise<StyleRef[]> {
  const rows = await sql(
    `select * from style_refs ${includeArchived ? "" : "where not archived"} order by kind, seeded desc, created_at`,
  );
  return rows.map(mapRef);
}

export function mapFlyer(r: Row): Flyer {
  return {
    id: String(r.id),
    title: String(r.title),
    brief: json(r.brief, {} as Flyer["brief"]),
    currentVersionId: (r.current_version_id as string) ?? null,
    eventId: (r.event_id as string) ?? null,
    archived: Boolean(r.archived),
    createdAt: iso(r.created_at),
    updatedAt: iso(r.updated_at),
  };
}

export function mapVersion(r: Row): FlyerVersion {
  return {
    id: String(r.id),
    flyerId: String(r.flyer_id),
    parentId: (r.parent_id as string) ?? null,
    label: String(r.label ?? ""),
    source: r.source as FlyerVersion["source"],
    spec: json(r.spec, {} as FlyerVersion["spec"]),
    critique: json(r.critique, null),
    hasThumb: Boolean(r.has_thumb),
    createdAt: iso(r.created_at),
  };
}

export const VERSION_COLS = "id, flyer_id, parent_id, label, source, spec, critique, (thumb is not null) as has_thumb, created_at";

export function newId(prefix: string) {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
}

export function jsonError(message: string, status = 400) {
  return Response.json({ error: message }, { status });
}
