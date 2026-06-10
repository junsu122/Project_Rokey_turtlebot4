-- Monitoring server schema for Supabase (Postgres).
-- Ported from monitor_server/db.py SQLite schema.
--
-- Changes vs SQLite:
--   * ISO-8601 text timestamps (at / last_seen)  -> timestamptz
--   * INTEGER PRIMARY KEY AUTOINCREMENT           -> bigint generated always as identity
--   * REAL                                        -> double precision
--   * resolved / escort_used kept as integer (0/1) for dashboard JS parity
--
-- The local bridge (FMS_BACKEND=supabase) writes here with the service_role key
-- (bypasses RLS). The external dashboard reads with the anon key under RLS.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists public.latest_robot_status (
    robot_id        text primary key,
    floor           integer,
    state           text,
    battery         integer,
    x               double precision,
    y               double precision,
    theta           double precision,
    current_task_id text,
    task_status     text,
    error_code      text,
    last_seen       timestamptz
);

create table if not exists public.robot_status_log (
    id          bigint generated always as identity primary key,
    robot_id    text,
    state       text,
    prev_state  text,
    task_id     text,
    task_status text,
    battery     integer,
    x           double precision,
    y           double precision,
    at          timestamptz
);

create table if not exists public.events (
    id           bigint generated always as identity primary key,
    msg_id       text,
    event_type   text,
    event_class  text,
    robot_id     text,
    confidence   double precision,
    x            double precision,
    y            double precision,
    floor        integer,
    snapshot_ref text,
    at           timestamptz,
    resolved     integer default 0,
    resolved_at  timestamptz,
    resolved_by  text
);

create table if not exists public.ui_usage_log (
    id               bigint generated always as identity primary key,
    source           text,
    language         text,
    customer_profile text,
    escort_used      integer default 0,
    at               timestamptz
);

create table if not exists public.monitor_counters (
    name       text primary key,
    value      integer default 0,
    updated_at timestamptz
);

-- ---------------------------------------------------------------------------
-- Indexes (mirror db.py)
-- ---------------------------------------------------------------------------

create index if not exists idx_status_log_robot on public.robot_status_log (robot_id, at desc);
create index if not exists idx_latest_robot_floor on public.latest_robot_status (floor);
create index if not exists idx_events_at        on public.events (at desc);
create index if not exists idx_usage_at         on public.ui_usage_log (at desc);
create index if not exists idx_events_type      on public.events (event_type, event_class);

-- ---------------------------------------------------------------------------
-- Realtime: push inserts/updates to subscribed dashboards
-- ---------------------------------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array['latest_robot_status','events','robot_status_log'] loop
    if not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t
    ) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- Row Level Security
--   * authenticated (logged-in operators): read-only on all monitoring tables
--   * authenticated: may resolve events (update resolved flags only)
--   * anon (public anon key alone): NO read -> login required to view
--   * writes (ingest) use service_role, which bypasses RLS entirely
-- ---------------------------------------------------------------------------

alter table public.latest_robot_status enable row level security;
alter table public.robot_status_log    enable row level security;
alter table public.events              enable row level security;
alter table public.ui_usage_log        enable row level security;
alter table public.monitor_counters    enable row level security;

do $$
declare t text;
begin
  foreach t in array array[
    'latest_robot_status','robot_status_log','events','ui_usage_log','monitor_counters'
  ] loop
    execute format(
      'drop policy if exists read_all on public.%I; '
      'create policy read_all on public.%I for select to authenticated using (true);',
      t, t);
  end loop;
end $$;

-- Logged-in operators may mark events resolved (UI "resolve" button).
drop policy if exists resolve_events on public.events;
create policy resolve_events on public.events
    for update to authenticated
    using (true)
    with check (true);
