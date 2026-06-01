alter table saved_jobs add column if not exists status text not null default 'Saved' check (status in ('Saved', 'Applied', 'Interviewing', 'Accepted', 'Rejected'));
