create table if not exists usage_events (
  id bigserial primary key,
  sub text not null,
  bucket text not null,
  created_at timestamptz not null default now()
);

create index if not exists usage_events_lookup_idx on usage_events (sub, bucket, created_at);
