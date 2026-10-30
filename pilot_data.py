import csv
import io
import re
from datetime import date
from urllib.parse import urlsplit, urlunsplit


PILOT_CSV_COLUMNS = (
    "source",
    "make",
    "model",
    "variant",
    "title",
    "year",
    "mileage_km",
    "price",
    "location",
    "url",
    "collected_at",
)


def _normalize_url(value):
    parts = urlsplit(value.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def parse_mileage_range(value):
    value = str(value).strip() if value is not None else ""
    if not value:
        return None, None

    mileage_parts = re.split(r"\s*[-–—]\s*", value)
    if len(mileage_parts) not in (1, 2):
        raise ValueError("mileage_km harus berupa angka atau rentang, contoh 95000-100000")

    mileages = []
    for part in mileage_parts:
        if not re.fullmatch(r"[0-9][0-9., ]*", part):
            raise ValueError("mileage_km harus berupa angka kilometer")
        digits = re.sub(r"[., ]", "", part)
        mileage = int(digits)
        if not 1 <= mileage <= 1_000_000:
            raise ValueError("kilometer harus antara 1 dan 1.000.000")
        mileages.append(mileage)

    if len(mileages) == 1:
        return mileages[0], mileages[0]
    if mileages[0] > mileages[1]:
        raise ValueError("batas minimum kilometer tidak boleh melebihi maksimum")
    return mileages[0], mileages[1]


def parse_pilot_csv(file_bytes):
    try:
        content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["File harus menggunakan encoding UTF-8."], 0

    try:
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return [], ["CSV kosong atau tidak memiliki header."], 0

        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        required_columns = set(PILOT_CSV_COLUMNS) - {"mileage_km"}
        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            return [], [f"Kolom wajib tidak ditemukan: {missing}."], 0

        records = []
        errors = []
        seen_urls = set()
        duplicate_count = 0
        current_year = date.today().year

        for row_number, row in enumerate(reader, start=2):
            values = {
                (key or "").strip().lower(): (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            if not any(values.values()):
                continue

            try:
                source = values["source"]
                make = values["make"]
                model = values["model"]
                variant = values["variant"]
                title = values["title"]
                location = values["location"]
                url = values["url"]
                if not all((source, make, model, title, location, url)):
                    raise ValueError(
                        "source, make, model, title, location, dan url wajib diisi"
                    )

                year = int(values["year"])
                if not 1980 <= year <= current_year + 1:
                    raise ValueError(f"tahun {year} di luar rentang yang didukung")

                mileage_min_km, mileage_max_km = parse_mileage_range(
                    values.get("mileage_km", "")
                )

                price_digits = re.sub(r"\D", "", values["price"])
                if not price_digits:
                    raise ValueError("harga harus berupa angka Rupiah penuh")
                price = int(price_digits)
                if price <= 30_000_000:
                    raise ValueError(
                        "harga harus di atas Rp 30.000.000 dalam Rupiah penuh"
                    )
                if price > 9_223_372_036_854_775_807:
                    raise ValueError("harga melebihi batas maksimum database")

                collected_date = date.fromisoformat(values["collected_at"])
                if collected_date > date.today():
                    raise ValueError("collected_at tidak boleh di masa depan")
                parsed_url = urlsplit(url)
                if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                    raise ValueError("url harus berupa tautan http:// atau https://")
            except (KeyError, ValueError) as error:
                errors.append(f"Baris {row_number}: {error}.")
                continue

            normalized_url = _normalize_url(url)
            if normalized_url in seen_urls:
                duplicate_count += 1
                continue
            seen_urls.add(normalized_url)

            records.append(
                {
                    "source": source,
                    "make": make.casefold(),
                    "model": model.casefold(),
                    "variant": variant,
                    "title": title,
                    "year": year,
                    "mileage_min_km": mileage_min_km,
                    "mileage_max_km": mileage_max_km,
                    "price": price,
                    "location": location,
                    "url": url,
                    "collected_at": collected_date.isoformat(),
                }
            )

    except csv.Error as error:
        return [], [f"CSV tidak dapat dibaca: {error}."], 0

    return records, errors, duplicate_count
