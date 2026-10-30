create table if not exists public.admin_users (
    user_id uuid primary key references auth.users (id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists public.vehicle_listings (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    make text not null,
    model text not null,
    variant text not null default '',
    title text not null,
    year integer,
    mileage_min_km integer,
    mileage_max_km integer,
    price bigint not null check (price > 30000000),
    location text,
    url text not null,
    normalized_url text not null unique,
    collected_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.vehicle_listings
    add column if not exists mileage_min_km integer;

alter table public.vehicle_listings
    add column if not exists mileage_max_km integer;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.vehicle_listings'::regclass
          and conname = 'vehicle_listings_mileage_range_check'
    ) then
        alter table public.vehicle_listings
            add constraint vehicle_listings_mileage_range_check
            check (
                (mileage_min_km is null and mileage_max_km is null)
                or (
                    mileage_min_km between 1 and 1000000
                    and mileage_max_km between mileage_min_km and 1000000
                )
            );
    end if;
end;
$$;

create index if not exists vehicle_listings_search_idx
    on public.vehicle_listings (make, model, year, collected_at desc);

create index if not exists vehicle_listings_location_idx
    on public.vehicle_listings (location);

create or replace function public.prepare_vehicle_listing_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    if tg_op = 'UPDATE' and new.location is null then
        new.location = old.location;
    end if;
    return new;
end;
$$;

drop trigger if exists vehicle_listings_prepare_update on public.vehicle_listings;
create trigger vehicle_listings_prepare_update
    before update on public.vehicle_listings
    for each row execute function public.prepare_vehicle_listing_update();

alter table public.admin_users enable row level security;
alter table public.vehicle_listings enable row level security;

create or replace function public.is_valuasioto_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.admin_users
        where user_id = (select auth.uid())
    );
$$;

revoke all on function public.is_valuasioto_admin() from public;
grant execute on function public.is_valuasioto_admin() to authenticated;

drop policy if exists "Admins can read their own admin record" on public.admin_users;
create policy "Admins can read their own admin record"
    on public.admin_users
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Authenticated users can read vehicle listings" on public.vehicle_listings;
drop policy if exists "Only admins can read vehicle listings" on public.vehicle_listings;
create policy "Only admins can read vehicle listings"
    on public.vehicle_listings
    for select
    to authenticated
    using ((select public.is_valuasioto_admin()));

drop policy if exists "Only admins can insert vehicle listings" on public.vehicle_listings;
create policy "Only admins can insert vehicle listings"
    on public.vehicle_listings
    for insert
    to authenticated
    with check ((select public.is_valuasioto_admin()));

drop policy if exists "Only admins can update vehicle listings" on public.vehicle_listings;
create policy "Only admins can update vehicle listings"
    on public.vehicle_listings
    for update
    to authenticated
    using ((select public.is_valuasioto_admin()))
    with check ((select public.is_valuasioto_admin()));

drop policy if exists "Only admins can delete vehicle listings" on public.vehicle_listings;
create policy "Only admins can delete vehicle listings"
    on public.vehicle_listings
    for delete
    to authenticated
    using ((select public.is_valuasioto_admin()));

grant select on public.vehicle_listings to authenticated;
grant insert, update, delete on public.vehicle_listings to authenticated;
grant select on public.admin_users to authenticated;
grant select, insert, update, delete on public.admin_users to service_role;
grant select, insert, update, delete on public.vehicle_listings to service_role;
