-- Table-level privileges for PostgREST roles.
--
-- RLS policies alone are NOT enough: each role still needs a table-level GRANT,
-- otherwise PostgREST returns 401/403 "permission denied for table". Supabase
-- usually applies these automatically, but apply them explicitly so the schema
-- is self-contained and portable.
--
--   service_role  : full DML (the LAN bridge ingests; bypasses RLS anyway)
--   authenticated : read-only (login required; RLS scopes rows; resolve via RPC)
--   anon          : nothing (no grant -> cannot read without logging in)

grant usage on schema public to authenticated, service_role;

grant select, insert, update, delete on all tables in schema public to service_role;
grant select on all tables in schema public to authenticated;

-- Any tables added later inherit the same grants.
alter default privileges in schema public
  grant select, insert, update, delete on tables to service_role;
alter default privileges in schema public
  grant select on tables to authenticated;
