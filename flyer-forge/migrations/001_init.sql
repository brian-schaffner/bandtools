create table if not exists band (
  id integer primary key default 1,
  name text not null default '',
  genre text not null default '',
  hometown text not null default '',
  updated_at timestamptz not null default now()
);

create table if not exists members (
  id text primary key,
  name text not null,
  role text not null default '',
  sort integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists assets (
  id text primary key,
  kind text not null,
  name text not null default '',
  photo_kind text,
  member_ids jsonb not null default '[]',
  mime text not null,
  width integer not null,
  height integer not null,
  byte_size integer not null,
  sha256 text not null,
  chunk_count integer not null,
  complete boolean not null default false,
  credit text not null default '',
  notes text not null default '',
  focal_x real not null default 0.5,
  focal_y real not null default 0.4,
  is_primary boolean not null default false,
  archived boolean not null default false,
  preview bytea,
  preview_mime text,
  created_at timestamptz not null default now()
);

create index if not exists assets_kind_idx on assets (kind, archived);

create table if not exists asset_chunks (
  asset_id text not null references assets (id) on delete cascade,
  idx integer not null,
  data bytea not null,
  primary key (asset_id, idx)
);

create table if not exists style_refs (
  id text primary key,
  kind text not null,
  title text not null,
  notes text not null default '',
  traits jsonb not null default '[]',
  recipe_id text,
  image_asset_id text,
  seeded boolean not null default false,
  archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists flyers (
  id text primary key,
  title text not null,
  brief jsonb not null,
  current_version_id text,
  archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists flyer_versions (
  id text primary key,
  flyer_id text not null references flyers (id) on delete cascade,
  parent_id text,
  label text not null default '',
  source text not null,
  spec jsonb not null,
  critique jsonb,
  thumb bytea,
  created_at timestamptz not null default now()
);

create index if not exists flyer_versions_flyer_idx on flyer_versions (flyer_id, created_at);
