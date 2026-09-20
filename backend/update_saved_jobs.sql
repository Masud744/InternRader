-- Run this query in Supabase Dashboard > SQL Editor if needed:

alter table saved_jobs add column if not exists notes text;
alter table saved_jobs add column if not exists applied_date text;

-- Add missing update policy on saved_jobs for RLS
drop policy if exists "Users can update their own saved jobs" on saved_jobs;
create policy "Users can update their own saved jobs" on saved_jobs
    for update using (auth.uid() = user_id);
