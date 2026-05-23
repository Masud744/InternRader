create extension if not exists pgcrypto;

create table if not exists internships (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    company text not null,
    location text,
    link text not null,
    source text not null,
    keyword text,
    posted_date text,
    scraped_date timestamptz not null default now()
);

create unique index if not exists internships_link_unique_idx
    on internships (link);

create index if not exists internships_scraped_date_idx
    on internships (scraped_date desc);

create table if not exists profiles (
    id uuid references auth.users(id) on delete cascade primary key,
    email text not null,
    full_name text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists saved_jobs (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) on delete cascade not null,
    internship_id uuid references internships(id) on delete cascade not null,
    created_at timestamptz default now(),
    unique(user_id, internship_id)
);

create index if not exists saved_jobs_user_id_idx on saved_jobs(user_id);

alter table profiles enable row level security;
alter table saved_jobs enable row level security;

create policy "Users can read their own profile" on profiles
    for select using (auth.uid() = id);

create policy "Users can update their own profile" on profiles
    for update using (auth.uid() = id);

create policy "Users can insert their own profile" on profiles
    for insert with check (auth.uid() = id);

create policy "Users can read their own saved jobs" on saved_jobs
    for select using (auth.uid() = user_id);

create policy "Users can insert their own saved jobs" on saved_jobs
    for insert with check (auth.uid() = user_id);

create policy "Users can delete their own saved jobs" on saved_jobs
    for delete using (auth.uid() = user_id);
