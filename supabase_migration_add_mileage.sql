alter table public.vehicle_listings
    add column if not exists mileage_min_km integer;

alter table public.vehicle_listings
    add column if not exists mileage_max_km integer;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'vehicle_listings'
          and column_name = 'mileage_km'
    ) then
        execute '
            update public.vehicle_listings
            set mileage_min_km = mileage_km,
                mileage_max_km = mileage_km
            where mileage_km is not null
              and mileage_min_km is null
              and mileage_max_km is null
        ';
    end if;

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
