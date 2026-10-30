import unittest
from types import SimpleNamespace

from supabase_data import deduplicate_listings, save_listings


class FakeTable:
    def __init__(self):
        self.payload = None

    def upsert(self, payload, on_conflict):
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return SimpleNamespace(data=self.payload)


class FakeDatabase:
    def __init__(self):
        self.listings = FakeTable()

    def table(self, name):
        if name != "vehicle_listings":
            raise AssertionError(f"Unexpected table: {name}")
        return self.listings


class SupabaseDataTests(unittest.TestCase):
    def test_deduplicates_listing_urls(self):
        records = [
            {"url": "https://example.com/avanza", "price": 175_000_000},
            {"url": "https://example.com/avanza/", "price": 176_000_000},
        ]

        self.assertEqual(len(deduplicate_listings(records)), 1)

    def test_saves_normalized_listing_payloads(self):
        db = FakeDatabase()
        record = {
            "source": "OLX",
            "make": "Toyota",
            "model": "Avanza",
            "variant": "G",
            "title": "Toyota Avanza G",
            "year": 2019,
            "mileage_min_km": 85_000,
            "mileage_max_km": 90_000,
            "price": 175_000_000,
            "location": "Jakarta Selatan",
            "url": "https://example.com/avanza",
            "collected_at": "2026-10-30T00:00:00+00:00",
        }

        saved = save_listings(db, [record, record])

        self.assertEqual(saved, 1)
        self.assertEqual(db.listings.on_conflict, "normalized_url")
        self.assertEqual(len(db.listings.payload), 1)
        self.assertEqual(db.listings.payload[0]["make"], "toyota")
        self.assertEqual(db.listings.payload[0]["mileage_min_km"], 85_000)
        self.assertEqual(db.listings.payload[0]["mileage_max_km"], 90_000)

    def test_saves_legacy_single_mileage_value_as_exact_range(self):
        db = FakeDatabase()
        record = {
            "source": "OLX",
            "make": "Toyota",
            "model": "Avanza",
            "title": "Toyota Avanza",
            "year": 2019,
            "mileage_km": "105368",
            "price": 175_000_000,
            "url": "https://example.com/avanza",
            "collected_at": "2026-10-30T00:00:00+00:00",
        }

        save_listings(db, [record])

        self.assertEqual(db.listings.payload[0]["mileage_min_km"], 105_368)
        self.assertEqual(db.listings.payload[0]["mileage_max_km"], 105_368)

    def test_rejects_non_http_listing_urls(self):
        record = {
            "source": "OLX",
            "make": "Toyota",
            "model": "Avanza",
            "title": "Toyota Avanza",
            "year": 2019,
            "price": 175_000_000,
            "location": None,
            "url": "not-a-url",
            "collected_at": "2026-10-30T00:00:00+00:00",
        }

        with self.assertRaises(ValueError):
            save_listings(FakeDatabase(), [record])

    def test_rejects_price_outside_postgres_bigint_range_before_upsert(self):
        record = {
            "source": "Carmudi",
            "make": "Toyota",
            "model": "Avanza",
            "title": "Toyota Avanza",
            "year": 2019,
            "price": 165_000_000_250_000_004_225_000,
            "url": "https://example.com/avanza",
            "collected_at": "2026-10-30T00:00:00+00:00",
        }

        with self.assertRaisesRegex(ValueError, "batas maksimum database"):
            save_listings(FakeDatabase(), [record])


if __name__ == "__main__":
    unittest.main()
