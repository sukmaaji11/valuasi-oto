import re

from pilot_data import parse_mileage_range


POSTGRES_BIGINT_MAX = 9_223_372_036_854_775_807
_RUPIAH_PATTERN = re.compile(r"Rp\s*([0-9][0-9.,]*)", re.IGNORECASE)
_MILEAGE_NUMBER = r"(?:[0-9]{1,3}(?:[., ][0-9]{3})+|[0-9]{1,7})"
_MILEAGE_VALUE = (
    rf"{_MILEAGE_NUMBER}(?:\s*[-–—]\s*{_MILEAGE_NUMBER})?"
)
_MILEAGE_RIBU_VALUE = r"[0-9]{1,3}(?:[.,][0-9]+)?"
_MILEAGE_LABEL_PATTERN = re.compile(
    rf"(?:kilometer|kilometre|mileage|odometer|jarak\s+tempuh|km)"
    rf"\s*[:=]?\s*({_MILEAGE_VALUE})"
    rf"\s*(?:km|kilometer|kilometre)?\b",
    re.IGNORECASE,
)
_MILEAGE_RIBU_PATTERN = re.compile(
    rf"(?:kilometer|kilometre|mileage|odometer|jarak\s+tempuh|km)"
    rf"\s*[:=]?\s*({_MILEAGE_RIBU_VALUE})\s*(?:ribu|rb)\b",
    re.IGNORECASE,
)
_MILEAGE_SUFFIX_PATTERN = re.compile(
    rf"\b({_MILEAGE_VALUE})\s*(?:kms?|kilometers?|kilometres?)\b",
    re.IGNORECASE,
)


def parse_listing_price(value):
    if value is None:
        return None

    text = str(value).strip()
    rupiah_match = _RUPIAH_PATTERN.search(text)
    if rupiah_match:
        amount_text = rupiah_match.group(1)
        grouped_amount = re.match(
            r"[0-9]{1,3}(?:[.,][0-9]{3})+", amount_text
        )
        if grouped_amount:
            end = grouped_amount.end()
            if end < len(amount_text) and amount_text[end].isdigit():
                return None
            text = grouped_amount.group(0)
        else:
            text = amount_text

    digits = re.sub(r"\D", "", text)
    if not digits:
        return None

    price = int(digits)
    if price > POSTGRES_BIGINT_MAX:
        return None
    return price


def extract_mileage_range(text):
    text = " ".join(str(text or "").split())
    match = _MILEAGE_RIBU_PATTERN.search(text)
    if match:
        value = float(match.group(1).replace(",", "."))
        mileage = int(value * 1_000)
        if 1 <= mileage <= 1_000_000:
            return mileage, mileage

    for pattern in (_MILEAGE_LABEL_PATTERN, _MILEAGE_SUFFIX_PATTERN):
        match = pattern.search(text)
        if match:
            try:
                return parse_mileage_range(match.group(1))
            except ValueError:
                continue
    return None, None


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_dicts(nested)


def _schema_mileage(vehicle):
    odometer = vehicle.get("mileageFromOdometer")
    if isinstance(odometer, dict):
        odometer = odometer.get("value")
    try:
        mileage = int(float(odometer))
    except (TypeError, ValueError):
        return None, None
    if not 1 <= mileage <= 1_000_000:
        return None, None
    return mileage, mileage


def _schema_location(offer):
    seller = offer.get("seller") or {}
    if isinstance(seller, list):
        seller = next((entry for entry in seller if isinstance(entry, dict)), {})
    address = seller.get("address") or {}
    if isinstance(address, str):
        return address.strip() or None
    if not isinstance(address, dict):
        return None

    parts = []
    for key in ("addressLocality", "addressRegion"):
        value = address.get(key)
        if isinstance(value, str) and value.strip():
            normalized = value.strip()
            if normalized.casefold() not in {part.casefold() for part in parts}:
                parts.append(normalized)
    return ", ".join(parts) or None


def extract_vehicle_schema_listings(json_data, source):
    listings = []
    seen_urls = set()
    for vehicle in _walk_dicts(json_data):
        title = vehicle.get("name")
        offers = vehicle.get("offers")
        if not isinstance(title, str) or not isinstance(offers, (dict, list)):
            continue
        if isinstance(offers, list):
            offers = next(
                (entry for entry in offers if isinstance(entry, dict)), {}
            )
        price = parse_listing_price(offers.get("price"))
        if price is None or price <= 30_000_000:
            continue

        detail_url = vehicle.get("mainEntityOfPage") or vehicle.get("url")
        if not isinstance(detail_url, str) or not detail_url.startswith(
            ("http://", "https://")
        ):
            continue
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)

        mileage_min_km, mileage_max_km = _schema_mileage(vehicle)
        if mileage_min_km is None:
            mileage_min_km, mileage_max_km = extract_mileage_range(
                " ".join(
                    part
                    for part in (
                        title,
                        str(vehicle.get("description") or ""),
                    )
                    if part
                )
            )

        year_match = re.search(r"\b(20[0-2][0-9]|19[8-9][0-9])\b", title)
        listings.append(
            {
                "source": source,
                "title": title.strip(),
                "price": price,
                "year": int(year_match.group(1)) if year_match else None,
                "mileage_min_km": mileage_min_km,
                "mileage_max_km": mileage_max_km,
                "location": _schema_location(offers),
                "url": detail_url,
            }
        )
    return listings


def extract_card_location(card):
    candidates = []
    for element in card.find_all(True):
        itemprop = str(element.get("itemprop") or "").casefold()
        marker = " ".join(
            str(value)
            for value in (
                element.get("data-testid"),
                element.get("class"),
                element.get("aria-label"),
                itemprop,
            )
            if value
        ).casefold()
        if not any(
            term in marker
            for term in ("location", "address", "locality", "wilayah", "lokasi")
        ):
            continue
        value = element.get("content") or element.get_text(" ", strip=True)
        value = re.sub(
            r"(?i)^\s*(?:lokasi|location|wilayah)\s*[:\-]\s*", "", str(value)
        )
        value = re.split(
            r"\s*(?:[•|]\s*|,\s*)(?=(?:\d+\s*(?:menit|jam|hari|minggu|bulan|tahun)|"
            r"hari ini|kemarin|today|yesterday)\b)",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        value = value.strip(" ,|•-")
        if 2 <= len(value) <= 100 and not re.fullmatch(
            r"(?i)(?:lokasi|location|wilayah|indonesia)", value
        ):
            candidates.append(value)

    locality = next(
        (
            str(element.get("content") or element.get_text(" ", strip=True)).strip()
            for element in card.find_all(True)
            if str(element.get("itemprop") or "").casefold() == "addresslocality"
        ),
        None,
    )
    region = next(
        (
            str(element.get("content") or element.get_text(" ", strip=True)).strip()
            for element in card.find_all(True)
            if str(element.get("itemprop") or "").casefold() == "addressregion"
        ),
        None,
    )
    if locality or region:
        parts = [part for part in (locality, region) if part]
        return ", ".join(dict.fromkeys(parts))
    return candidates[0] if candidates else None
