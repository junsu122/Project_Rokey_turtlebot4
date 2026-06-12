-- Aggregation RPCs that replace the heavy SQL in monitor_server/api.py.
-- The dashboard calls these via supabase.rpc(...) instead of Flask /api/* routes.
--
-- All are SECURITY DEFINER so they run with the owner's rights under RLS, and
-- granted to anon + authenticated (read paths) / authenticated (resolve).

-- ---------------------------------------------------------------------------
-- Robot reference metadata (config.ROBOTS in config.py). Informational only.
-- ---------------------------------------------------------------------------

create table if not exists public.robots (
    robot_id  text primary key,
    namespace text,
    floor     integer,
    ordinal   integer            -- display order (config.ROBOT_IDS order)
);

insert into public.robots (robot_id, namespace, floor, ordinal) values
    ('robot2', '/robot2', 1, 0),
    ('robot4', '/robot4', 2, 1)
on conflict (robot_id) do update
    set namespace = excluded.namespace,
        floor     = excluded.floor,
        ordinal   = excluded.ordinal;

alter table public.robots enable row level security;
drop policy if exists read_all on public.robots;
create policy read_all on public.robots for select to authenticated using (true);
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'robots'
  ) then
    alter publication supabase_realtime add table public.robots;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- /api/robots  -> get_robots(timeout_s)
-- Merges known robots (public.robots) with latest_robot_status, computing
-- age_s and online exactly like api._robot_snapshots.
-- ---------------------------------------------------------------------------

create or replace function public.get_robots(timeout_s double precision default 10.0)
returns jsonb
language sql stable security definer set search_path = public as $$
  with merged as (
    select
      coalesce(r.robot_id, s.robot_id)                              as robot_id,
      r.floor, r.namespace,
      s.state, s.battery, s.x, s.y, s.theta,
      s.current_task_id, s.task_status, s.error_code, s.last_seen,
      coalesce(r.ordinal, 9999)                                     as ordinal,
      case when s.last_seen is null then null
           else extract(epoch from (now() - s.last_seen)) end       as age_s
    from public.robots r
    full outer join public.latest_robot_status s on s.robot_id = r.robot_id
  )
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'robot_id', robot_id,
      'floor', floor,
      'namespace', namespace,
      'state', state,
      'battery', battery,
      'pose', jsonb_build_object('x', x, 'y', y, 'theta', theta),
      'current_task_id', current_task_id,
      'task_status', task_status,
      'error_code', error_code,
      'last_seen', last_seen,
      'age_s', age_s,
      'online', age_s is not null and age_s <= timeout_s
    ) order by ordinal, robot_id
  ), '[]'::jsonb)
  from merged;
$$;

-- ---------------------------------------------------------------------------
-- /api/stats  -> get_stats()
-- Mirrors api.stats(): event/class counts, language+profile usage, counters.
-- ---------------------------------------------------------------------------

create or replace function public.get_stats()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  -- passenger filter: COALESCE(source,'INTERACTING') NOT IN ('ESCORT','CANCEL')
  by_type      jsonb;
  by_class     jsonb;
  languages    jsonb;
  profiles     jsonb;
  counters     jsonb;
  usage_count  int;
  escort_count int;
  vulnerable   int;
  ev_total     int;
  ev_active    int;
  log_total    int;
  robot_known  int;
begin
  select coalesce(jsonb_object_agg(t, c), '{}'::jsonb) into by_type
  from (select coalesce(event_type,'UNKNOWN') t, count(*) c from public.events group by 1) q;

  select coalesce(jsonb_object_agg(event_class, c), '{}'::jsonb) into by_class
  from (select event_class, count(*) c from public.events
        where event_class is not null group by 1) q;

  select jsonb_build_object(
    'ko', coalesce(sum(case when lang='ko' then c end),0),
    'zh', coalesce(sum(case when lang='zh' then c end),0),
    'ja', coalesce(sum(case when lang='ja' then c end),0),
    'en', coalesce(sum(case when lang='en' then c end),0),
    'etc',coalesce(sum(case when lang not in ('ko','zh','ja','en') then c end),0)
  ) into languages
  from (
    select lower(substr(coalesce(language,''),1,2)) lang, count(*) c
    from public.ui_usage_log
    where coalesce(source,'INTERACTING') not in ('ESCORT','CANCEL')
    group by 1
  ) q;

  select coalesce(jsonb_object_agg(coalesce(customer_profile,'UNKNOWN'), c), '{}'::jsonb)
    into profiles
  from (select customer_profile, count(*) c from public.ui_usage_log
        where coalesce(source,'INTERACTING') not in ('ESCORT','CANCEL')
        group by 1) q;

  select coalesce(jsonb_object_agg(name, value), '{}'::jsonb) into counters
  from public.monitor_counters;

  select count(*) into usage_count from public.ui_usage_log
    where coalesce(source,'INTERACTING') not in ('ESCORT','CANCEL');
  select count(*) into escort_count from public.ui_usage_log
    where escort_used = 1 or source = 'ESCORT';

  select count(*) into ev_total  from public.events;
  select count(*) into ev_active from public.events where resolved = 0;
  select count(*) into log_total from public.robot_status_log;
  select count(*) into robot_known from (
    select robot_id from public.robots
    union select robot_id from public.latest_robot_status
  ) q;

  vulnerable :=
      coalesce((profiles->>'ELDERLY')::int, 0)
    + coalesce((profiles->>'VISUALLY_IMPAIRED')::int, 0)
    + coalesce((counters->>'vulnerable')::int, 0);

  return jsonb_build_object(
    'robots', jsonb_build_object('known', robot_known, 'status_log', log_total),
    'events', jsonb_build_object(
      'total', ev_total, 'active', ev_active,
      'by_type', by_type, 'by_class', by_class),
    'usage', jsonb_build_object(
      'passengers', usage_count + coalesce((counters->>'passengers')::int,0),
      'escorts',    escort_count + coalesce((counters->>'escorts')::int,0),
      'languages',  languages,
      'profiles',   profiles,
      'vulnerable', vulnerable)
  );
end $$;

-- ---------------------------------------------------------------------------
-- /api/search  -> search_monitor(q, kind, lim)
-- ---------------------------------------------------------------------------

create or replace function public.search_monitor(
  q text, kind text default 'all', lim int default 30)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  like_q  text := '%' || q || '%';
  ev      jsonb := '[]'::jsonb;
  st      jsonb := '[]'::jsonb;
  total   int := 0;
  res     jsonb := '{}'::jsonb;
begin
  if q is null or btrim(q) = '' then
    return jsonb_build_object('q', q, 'kind', kind, 'total', 0, 'results', '{}'::jsonb);
  end if;

  if kind in ('all','events') then
    select coalesce(jsonb_agg(row_to_json(e)), '[]'::jsonb) into ev from (
      select id, event_type, event_class, robot_id, confidence, floor, at, resolved
      from public.events
      where event_type ilike like_q or event_class ilike like_q or robot_id ilike like_q
      order by at desc limit lim) e;
    res := res || jsonb_build_object('events', ev);
  end if;

  if kind in ('all','status') then
    select coalesce(jsonb_agg(row_to_json(s)), '[]'::jsonb) into st from (
      select robot_id, state, prev_state, task_status, battery, at
      from public.robot_status_log
      where robot_id ilike like_q or state ilike like_q or task_status ilike like_q
      order by at desc limit lim) s;
    res := res || jsonb_build_object('status', st);
  end if;

  total := jsonb_array_length(coalesce(res->'events','[]'::jsonb))
         + jsonb_array_length(coalesce(res->'status','[]'::jsonb));
  return jsonb_build_object('q', q, 'kind', kind, 'total', total, 'results', res);
end $$;

-- ---------------------------------------------------------------------------
-- /api/system  -> get_system(timeout_s)
-- Row counts + online/total. ROS topic/db fields are filled client-side.
-- ---------------------------------------------------------------------------

create or replace function public.get_system(timeout_s double precision default 10.0)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  total  int;
  online int;
begin
  select count(*),
         count(*) filter (
           where last_seen is not null
             and extract(epoch from (now() - last_seen)) <= timeout_s)
    into total, online
  from public.latest_robot_status;

  return jsonb_build_object(
    'robots', jsonb_build_object(
      'total', total, 'online', online,
      'offline', total - online, 'timeout_s', timeout_s),
    'counts', jsonb_build_object(
      'latest_robot_status', (select count(*) from public.latest_robot_status),
      'robot_status_log',    (select count(*) from public.robot_status_log),
      'events',              (select count(*) from public.events),
      'ui_usage_log',        (select count(*) from public.ui_usage_log),
      'monitor_counters',    (select count(*) from public.monitor_counters))
  );
end $$;

-- ---------------------------------------------------------------------------
-- /api/events/<id>/resolve  -> resolve_event(event_id)
-- Logged-in operator marks an event resolved; resolved_by = their email.
-- ---------------------------------------------------------------------------

create or replace function public.resolve_event(event_id bigint)
returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  already boolean;
  who text := coalesce(auth.jwt() ->> 'email', 'operator');
begin
  select resolved = 1 into already from public.events where id = event_id;
  if not found then
    return jsonb_build_object('error', 'event not found');
  end if;
  if already then
    return jsonb_build_object('ok', true, 'already', true);
  end if;
  update public.events
     set resolved = 1, resolved_at = now(), resolved_by = who
   where id = event_id;
  return jsonb_build_object('ok', true, 'event_id', event_id, 'resolved_by', who);
end $$;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

grant execute on function public.get_robots(double precision) to authenticated;
grant execute on function public.get_stats()                  to authenticated;
grant execute on function public.search_monitor(text, text, int) to authenticated;
grant execute on function public.get_system(double precision)    to authenticated;
grant execute on function public.resolve_event(bigint)        to authenticated;
