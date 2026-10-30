import unittest

from pilot_data import parse_pilot_csv


class ParsePilotCsvTests(unittest.TestCase):
    def test_parses_rupiah_and_required_metadata(self):
        content = (
            "source,make,model,variant,title,year,price,location,url,collected_at\n"
            "Facebook Marketplace,Toyota,Avanza,G,Toyota Avanza G,2019,Rp 175.000.000,"
            "Jakarta Selatan,https://example.com/avanza,2026-10-30\n"
        )

        records, errors, duplicate_count = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(errors, [])
        self.assertEqual(duplicate_count, 0)
        self.assertEqual(records[0]["price"], 175000000)
        self.assertEqual(records[0]["year"], 2019)
        self.assertEqual(records[0]["location"], "Jakarta Selatan")
        self.assertEqual(records[0]["make"], "toyota")
        self.assertEqual(records[0]["model"], "avanza")

    def test_parses_optional_mileage_with_thousands_separator(self):
        content = (
            "source,make,model,variant,title,year,mileage_km,price,location,url,collected_at\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,85.000,175000000,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
        )

        records, errors, _ = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(errors, [])
        self.assertEqual(records[0]["mileage_min_km"], 85000)
        self.assertEqual(records[0]["mileage_max_km"], 85000)

    def test_parses_mileage_range(self):
        content = (
            "source,make,model,variant,title,year,mileage_km,price,location,url,collected_at\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,95000-100000,175000000,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
        )

        records, errors, _ = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(errors, [])
        self.assertEqual(records[0]["mileage_min_km"], 95000)
        self.assertEqual(records[0]["mileage_max_km"], 100000)

    def test_rejects_reversed_mileage_range(self):
        content = (
            "source,make,model,variant,title,year,mileage_km,price,location,url,collected_at\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,100000-95000,175000000,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
        )

        records, errors, _ = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(records, [])
        self.assertIn("tidak boleh melebihi maksimum", errors[0])

    def test_old_csv_without_mileage_column_remains_supported(self):
        content = (
            "source,make,model,variant,title,year,price,location,url,collected_at\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,175000000,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
        )

        records, errors, _ = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(errors, [])
        self.assertIsNone(records[0]["mileage_min_km"])
        self.assertIsNone(records[0]["mileage_max_km"])

    def test_rejects_mileage_outside_supported_range_or_non_numeric_value(self):
        content = (
            "source,make,model,variant,title,year,mileage_km,price,location,url,collected_at\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,0,175000000,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,unknown,175000000,Jakarta,"
            "https://example.com/avanza-2,2026-10-30\n"
        )

        records, errors, _ = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(records, [])
        self.assertEqual(len(errors), 2)

    def test_rejects_invalid_rows_and_deduplicates_url(self):
        content = (
            "source,make,model,variant,title,year,price,location,url,collected_at\n"
            "Facebook Marketplace,Toyota,Avanza,G,Toyota Avanza G,2019,175000000,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
            "OLX,Toyota,Avanza,G,Toyota Avanza G,2019,175000000,Jakarta,"
            "https://example.com/avanza/,2026-10-30\n"
            "Facebook Marketplace,Toyota,Avanza,,Invalid,unknown,price,,not-a-url,2026-10-30\n"
        )

        records, errors, duplicate_count = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(len(records), 1)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Baris 4", errors[0])

    def test_reports_missing_columns(self):
        content = b"title,price\nAvanza,175000000\n"

        records, errors, duplicate_count = parse_pilot_csv(content)

        self.assertEqual(records, [])
        self.assertEqual(duplicate_count, 0)
        self.assertIn("collected_at", errors[0])

    def test_rejects_price_entered_in_millions_instead_of_full_rupiah(self):
        content = (
            "source,make,model,variant,title,year,price,location,url,collected_at\n"
            "Facebook Marketplace,Toyota,Avanza,G,Toyota Avanza G,2019,175,Jakarta,"
            "https://example.com/avanza,2026-10-30\n"
        )

        records, errors, duplicate_count = parse_pilot_csv(content.encode("utf-8"))

        self.assertEqual(records, [])
        self.assertEqual(duplicate_count, 0)
        self.assertIn("Rupiah penuh", errors[0])


if __name__ == "__main__":
    unittest.main()
