create table if not exists events (
  id text primary key,
  title text not null default '',
  date text not null,
  status text not null default 'confirmed',
  venue text not null default '',
  city text not null default '',
  address text not null default '',
  doors text not null default '',
  show_time text not null default '',
  price text not null default '',
  ages text not null default '',
  support jsonb not null default '[]',
  tickets text not null default '',
  contact_name text not null default '',
  contact_phone text not null default '',
  contact_email text not null default '',
  deal text not null default '',
  notes text not null default '',
  external_uid text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists events_date_idx on events (date);

create table if not exists event_schedule (
  id text primary key,
  event_id text not null references events (id) on delete cascade,
  time text not null default '',
  label text not null,
  kind text not null default 'other',
  notes text not null default '',
  sort integer not null default 0
);

create index if not exists event_schedule_event_idx on event_schedule (event_id, sort);

create table if not exists setlists (
  id text primary key,
  event_id text references events (id) on delete set null,
  name text not null,
  notes text not null default '',
  items jsonb not null default '[]',
  source text not null default 'manual',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists setlists_event_idx on setlists (event_id);

alter table flyers add column if not exists event_id text references events (id) on delete set null;
create index if not exists flyers_event_idx on flyers (event_id);

-- Existing flyers each become (or join) a calendar event keyed on date + venue.
insert into events (id, title, date, venue, city, doors, show_time, price, ages, support, tickets)
select distinct on (f.brief->>'date', lower(coalesce(f.brief->>'venue', '')))
  'event_' || substr(md5(f.id), 1, 16),
  coalesce(f.brief->>'headline', ''),
  f.brief->>'date',
  coalesce(f.brief->>'venue', ''),
  coalesce(f.brief->>'city', ''),
  coalesce(f.brief->>'doors', ''),
  coalesce(f.brief->>'showTime', ''),
  coalesce(f.brief->>'price', ''),
  coalesce(f.brief->>'ages', ''),
  coalesce(f.brief->'support', '[]'::jsonb),
  coalesce(f.brief->>'tickets', '')
from flyers f
where f.event_id is null and coalesce(f.brief->>'date', '') <> ''
order by f.brief->>'date', lower(coalesce(f.brief->>'venue', '')), f.created_at
on conflict do nothing;

update flyers f set event_id = e.id
from events e
where f.event_id is null
  and e.date = f.brief->>'date'
  and lower(e.venue) = lower(coalesce(f.brief->>'venue', ''));
