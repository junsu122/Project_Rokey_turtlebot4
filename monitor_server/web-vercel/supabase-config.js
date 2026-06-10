// Public Supabase config for the dashboard (Vercel static site).
//
// These two values are PUBLIC by design (the anon key is meant to ship to
// browsers). Access is still protected: RLS grants reads only to logged-in
// (authenticated) users, so the anon key alone cannot read any data.
//
// Fill in from Supabase: Project Settings > API.
window.SUPABASE_CONFIG = {
  url:     "https://dnrfcywcrlymifpuwayc.supabase.co",
  anonKey: "sb_publishable_vAOdjJ89RFoAfZt6sDCMuw__yJ-9Ynk",
  statusTimeout: 10,   // seconds; matches FMS_STATUS_TIMEOUT on the bridge
};
