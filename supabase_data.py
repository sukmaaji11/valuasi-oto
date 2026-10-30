from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from supabase import create_client
from pilot_data import parse_mileage_range
from scraper_utils import POSTGRES_BIGINT_MAX


TABLE_LISTINGS = "vehicle_listings"


def create_database_clients(config):
    required = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(
            "Konfigurasi Supabase belum lengkap: " + ", ".join(missing)
        )

    url = config["SUPABASE_URL"]
    return (
        create_client(url, config["SUPABASE_ANON_KEY"]),
        create_client(url, config["SUPABASE_SERVICE_ROLE_KEY"]),
    )


def authenticate_admin(auth_client, db_client, email, password):
    response = auth_client.auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    user = response.user
    if user is None:
        raise RuntimeError("Login tidak menghasilkan identitas pengguna.")

    admin = (
        db_client.table("admin_users")
        .select("user_id")
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )
    if admin.data is None:
        auth_client.auth.sign_out()
        raise PermissionError("Akun berhasil login, tetapi belum terdaftar sebagai admin.")
    return {"id": user.id, "email": user.email}


def _normalize_url(value):
    parts = urlsplit(value.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def _listing_payload(record):
    url = record.get("url", "").strip()
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise ValueError(f"URL listing tidak valid: {url}")
    required = ("source", "make", "model", "title", "collected_at")
    if any(not str(record.get(key, "")).strip() for key in required):
        raise ValueError("Listing memerlukan sumber, merek, model, judul, dan tanggal.")
    price = int(record["price"])
    if price <= 30_000_000:
        raise ValueError("Harga listing harus lebih dari Rp 30.000.000.")
    if price > POSTGRES_BIGINT_MAX:
        raise ValueError("Harga listing melebihi batas maksimum database.")
    if "mileage_min_km" in record or "mileage_max_km" in record:
        mileage_min_km = record.get("mileage_min_km")
        mileage_max_km = record.get("mileage_max_km")
        if (mileage_min_km is None) != (mileage_max_km is None):
            raise ValueError("Batas minimum dan maksimum kilometer harus diisi bersama.")
        if mileage_min_km is not None:
            mileage_min_km = int(mileage_min_km)
            mileage_max_km = int(mileage_max_km)
            if (
                not 1 <= mileage_min_km <= mileage_max_km <= 1_000_000
            ):
                raise ValueError("Rentang kilometer harus antara 1 dan 1.000.000.")
    else:
        mileage_min_km, mileage_max_km = parse_mileage_range(
            record.get("mileage_km")
        )
    return {
        "source": record["source"].strip(),
        "make": record["make"].strip().casefold(),
        "model": record["model"].strip().casefold(),
        "variant": record.get("variant", "").strip(),
        "title": record["title"].strip(),
        "year": record.get("year"),
        "mileage_min_km": mileage_min_km,
        "mileage_max_km": mileage_max_km,
        "price": price,
        "location": (record.get("location") or "").strip() or None,
        "url": url,
        "normalized_url": _normalize_url(url),
        "collected_at": record["collected_at"],
    }


def save_listings(db_client, records):
    unique_payloads = {}
    for record in records:
        payload = _listing_payload(record)
        unique_payloads.setdefault(payload["normalized_url"], payload)
    payloads = list(unique_payloads.values())
    if not payloads:
        return 0
    result = (
        db_client.table(TABLE_LISTINGS)
        .upsert(
            payloads,
            on_conflict="normalized_url",
        )
        .execute()
    )
    return len(result.data or [])


def get_fresh_listings(
    db_client,
    make,
    model,
    min_year,
    max_year,
    location,
    freshness_hours=24,
):
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
    ).isoformat()
    query = (
        db_client.table(TABLE_LISTINGS)
        .select(
            "source,make,model,variant,title,year,mileage_min_km,mileage_max_km,price,location,url,collected_at"
        )
        .eq("make", make.strip().casefold())
        .eq("model", model.strip().casefold())
        .gte("year", min_year)
        .lte("year", max_year)
        .gte("collected_at", cutoff)
    )
    if location.strip().casefold() not in ("", "semua wilayah", "seluruh indonesia"):
        query = query.ilike("location", f"%{location.strip()}%")
    return query.order("collected_at", desc=True).execute().data or []


def deduplicate_listings(records):
    seen = set()
    unique = []
    for record in records:
        url = record.get("url", "")
        key = _normalize_url(url) if url else (
            record.get("make"),
            record.get("model"),
            record.get("year"),
            record.get("price"),
            record.get("title", "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique
