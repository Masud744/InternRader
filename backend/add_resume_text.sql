-- Run this SQL in the Supabase SQL Editor:
-- Dashboard > SQL Editor > New Query > Paste this > Run

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS resume_text text;
