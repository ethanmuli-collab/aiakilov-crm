-- ============================================================================
-- AIAKILOV CRM - PostgreSQL / Supabase schema
--
-- SAFETY: every object is prefixed `aiakilov_` and isolated from any other
-- schema in the project. This file contains NO DROP statements, no CASCADE and
-- no TRUNCATE. Applying it can only ADD objects.
-- ============================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------- profiles
-- CRM staff only. Students are business records, not login users.
create table if not exists aiakilov_profiles (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid unique,                        -- references auth.users(id)
    email       text unique not null,
    full_name   text not null,
    role        text not null default 'SALES'
                check (role in ('ADMIN','SALES','COURSE_MANAGER',
                                'LECTURER','MARKETING','MANAGEMENT')),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- courses
create table if not exists aiakilov_courses (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    description text,
    price       numeric(10,2) not null check (price >= 0),
    start_date  date,
    end_date    date,
    lecturer    text,
    capacity    integer check (capacity > 0),
    hours       integer check (hours > 0),
    difficulty  text,
    status      text not null default 'active'
                check (status in ('active','draft','archived')),
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- leads
create table if not exists aiakilov_leads (
    id                     uuid primary key default gen_random_uuid(),
    first_name             text not null,
    last_name              text not null,
    email                  text,
    phone                  text,
    age                    integer check (age between 14 and 120),
    city                   text,
    occupation             text,
    education              text,
    course_interest        text,
    lead_source            text check (lead_source in
                             ('Facebook','Instagram','Google Ads','Website',
                              'Referral','Organic','WhatsApp','Event')),
    status                 text not null default 'New' check (status in
                             ('New','Contacted','Interested','Follow-up',
                              'Counseling','Offer Sent','Won','Lost')),
    budget                 numeric(10,2) check (budget >= 0),
    preferred_schedule     text,
    previous_ai_experience boolean not null default false,
    interaction_count      integer not null default 0 check (interaction_count >= 0),
    assigned_sales_rep     text,
    notes                  text,
    purchased              boolean not null default false,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

create index if not exists idx_aiakilov_leads_status  on aiakilov_leads(status);
create index if not exists idx_aiakilov_leads_source  on aiakilov_leads(lead_source);
create index if not exists idx_aiakilov_leads_course  on aiakilov_leads(course_interest);
create index if not exists idx_aiakilov_leads_rep     on aiakilov_leads(assigned_sales_rep);
create index if not exists idx_aiakilov_leads_created on aiakilov_leads(created_at desc);

-- ---------------------------------------------------------------- activities
create table if not exists aiakilov_lead_activities (
    id            uuid primary key default gen_random_uuid(),
    lead_id       uuid not null references aiakilov_leads(id) on delete cascade,
    activity_type text not null,
    description   text,
    created_by    text,
    created_at    timestamptz not null default now()
);
create index if not exists idx_aiakilov_activities_lead on aiakilov_lead_activities(lead_id);

-- ---------------------------------------------------------------- follow-ups
create table if not exists aiakilov_followups (
    id         uuid primary key default gen_random_uuid(),
    lead_id    uuid not null references aiakilov_leads(id) on delete cascade,
    title      text not null,
    due_date   date,
    done       boolean not null default false,
    created_at timestamptz not null default now()
);
create index if not exists idx_aiakilov_followups_lead on aiakilov_followups(lead_id);

-- ---------------------------------------------------------------- students
create table if not exists aiakilov_students (
    id         uuid primary key default gen_random_uuid(),
    lead_id    uuid references aiakilov_leads(id) on delete set null,
    first_name text not null,
    last_name  text not null,
    email      text,
    phone      text,
    city       text,
    created_at timestamptz not null default now()
);
create index if not exists idx_aiakilov_students_lead on aiakilov_students(lead_id);

-- ---------------------------------------------------------------- enrollments
-- A student may enrol in several courses; enrolment is its own entity.
create table if not exists aiakilov_enrollments (
    id              uuid primary key default gen_random_uuid(),
    student_id      uuid not null references aiakilov_students(id) on delete cascade,
    course_id       uuid not null references aiakilov_courses(id) on delete restrict,
    enrollment_date date not null default current_date,
    status          text not null default 'active'
                    check (status in ('active','completed','cancelled')),
    price           numeric(10,2) check (price >= 0),
    payment_status  text not null default 'pending'
                    check (payment_status in ('pending','paid','failed','refunded')),
    created_at      timestamptz not null default now(),
    unique (student_id, course_id)
);
create index if not exists idx_aiakilov_enr_student on aiakilov_enrollments(student_id);
create index if not exists idx_aiakilov_enr_course  on aiakilov_enrollments(course_id);
create index if not exists idx_aiakilov_enr_payment on aiakilov_enrollments(payment_status);

-- ---------------------------------------------------------------- payments
-- Simulated only. No real payment provider is connected.
create table if not exists aiakilov_payments (
    id            uuid primary key default gen_random_uuid(),
    enrollment_id uuid not null references aiakilov_enrollments(id) on delete cascade,
    amount        numeric(10,2) not null check (amount >= 0),
    method        text,
    paid_at       date,
    created_at    timestamptz not null default now()
);
create index if not exists idx_aiakilov_payments_enr on aiakilov_payments(enrollment_id);

-- ---------------------------------------------------------------- invoices
-- EDUCATIONAL DEMO DOCUMENTS ONLY. These are NOT legally compliant Israeli
-- tax invoices and must not be used for any accounting or legal purpose.
create table if not exists aiakilov_invoices (
    id             uuid primary key default gen_random_uuid(),
    invoice_number text unique not null,
    enrollment_id  uuid not null references aiakilov_enrollments(id) on delete cascade,
    student_id     uuid not null references aiakilov_students(id) on delete cascade,
    course_id      uuid not null references aiakilov_courses(id) on delete restrict,
    amount         numeric(10,2) not null check (amount >= 0),
    issue_date     date not null default current_date,
    payment_status text not null default 'pending'
                   check (payment_status in ('pending','paid','failed','refunded')),
    created_at     timestamptz not null default now()
);
create index if not exists idx_aiakilov_invoices_student on aiakilov_invoices(student_id);

-- ---------------------------------------------------------------- predictions
create table if not exists aiakilov_ml_predictions (
    id          uuid primary key default gen_random_uuid(),
    lead_id     uuid not null references aiakilov_leads(id) on delete cascade,
    model_key   text not null,
    probability numeric(5,4) not null check (probability between 0 and 1),
    priority    text check (priority in ('high','medium','low')),
    created_at  timestamptz not null default now()
);
create index if not exists idx_aiakilov_pred_lead on aiakilov_ml_predictions(lead_id);

-- ============================================================================
-- Row Level Security
--
-- This CRM is internal-only: every table is readable by authenticated staff and
-- writable through the application. Fine-grained per-role write policies are
-- documented below and can be layered on without changing the app.
-- ============================================================================

alter table aiakilov_profiles        enable row level security;
alter table aiakilov_courses         enable row level security;
alter table aiakilov_leads           enable row level security;
alter table aiakilov_lead_activities enable row level security;
alter table aiakilov_followups       enable row level security;
alter table aiakilov_students        enable row level security;
alter table aiakilov_enrollments     enable row level security;
alter table aiakilov_payments        enable row level security;
alter table aiakilov_invoices        enable row level security;
alter table aiakilov_ml_predictions  enable row level security;

-- Helper: the calling user's CRM role.
-- SECURITY INVOKER, not DEFINER: aiakilov_read_authenticated already lets any
-- authenticated user select all of aiakilov_profiles, so this function never
-- needs elevated privileges. DEFINER would make it directly callable via
-- /rest/v1/rpc/aiakilov_current_role with no added benefit - a real (if low
-- severity) finding the Supabase security linter flags.
create or replace function aiakilov_current_role()
returns text
language sql
stable
security invoker
set search_path = public
as $$
    select role from aiakilov_profiles where user_id = auth.uid()
$$;

-- Baseline: any authenticated staff member may read.
do $$
declare t text;
begin
    foreach t in array array[
        'aiakilov_profiles','aiakilov_courses','aiakilov_leads',
        'aiakilov_lead_activities','aiakilov_followups','aiakilov_students',
        'aiakilov_enrollments','aiakilov_payments','aiakilov_invoices',
        'aiakilov_ml_predictions']
    loop
        if not exists (
            select 1 from pg_policies
            where schemaname = 'public' and tablename = t
              and policyname = 'aiakilov_read_authenticated'
        ) then
            execute format(
                'create policy aiakilov_read_authenticated on %I
                 for select to authenticated using (true)', t);
        end if;
    end loop;
end $$;

-- Write policies, role-scoped.
do $$
begin
    if not exists (select 1 from pg_policies
                   where tablename = 'aiakilov_leads'
                     and policyname = 'aiakilov_leads_write_sales') then
        create policy aiakilov_leads_write_sales on aiakilov_leads
            for all to authenticated
            using (aiakilov_current_role() in ('ADMIN','SALES'))
            with check (aiakilov_current_role() in ('ADMIN','SALES'));
    end if;

    if not exists (select 1 from pg_policies
                   where tablename = 'aiakilov_courses'
                     and policyname = 'aiakilov_courses_write_manager') then
        create policy aiakilov_courses_write_manager on aiakilov_courses
            for all to authenticated
            using (aiakilov_current_role() in ('ADMIN','COURSE_MANAGER'))
            with check (aiakilov_current_role() in ('ADMIN','COURSE_MANAGER'));
    end if;

    if not exists (select 1 from pg_policies
                   where tablename = 'aiakilov_enrollments'
                     and policyname = 'aiakilov_enrollments_write_manager') then
        create policy aiakilov_enrollments_write_manager on aiakilov_enrollments
            for all to authenticated
            using (aiakilov_current_role() in ('ADMIN','COURSE_MANAGER'))
            with check (aiakilov_current_role() in ('ADMIN','COURSE_MANAGER'));
    end if;
end $$;
