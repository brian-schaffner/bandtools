alter table band add column if not exists home_address text not null default '';
alter table band add column if not exists no_trailer_venues jsonb not null default '["Stevie Ray''s"]'::jsonb;
alter table events add column if not exists drive_minutes integer;
alter table events add column if not exists trailer text not null default 'auto';
alter table event_schedule add column if not exists end_time text not null default '';
