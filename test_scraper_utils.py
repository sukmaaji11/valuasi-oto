import unittest

from bs4 import BeautifulSoup

from scraper_utils import (
    extract_card_location,
    extract_mileage_range,
    extract_vehicle_schema_listings,
    parse_listing_price,
)


class ExtractMileageRangeTests(unittest.TestCase):
    def test_extracts_single_odometer_reading(self):
        self.assertEqual(
            extract_mileage_range("Toyota Avanza 2016 • Kilometer: 105.368 km"),
            (105_368, 105_368),
        )

    def test_extracts_range_with_km_suffix(self):
        self.assertEqual(
            extract_mileage_range("Toyota Avanza • 95.000-100.000 km"),
            (95_000, 100_000),
        )

    def test_extracts_range_with_km_label(self):
        self.assertEqual(
            extract_mileage_range("KM: 65.000 – 70.000"),
            (65_000, 70_000),
        )

    def test_extracts_thousands_from_indonesian_ribu_label(self):
        self.assertEqual(
            extract_mileage_range("2017 Honda Brio Kilometer 40 ribu"),
            (40_000, 40_000),
        )

    def test_returns_empty_values_when_mileage_is_missing(self):
        self.assertEqual(
            extract_mileage_range("Toyota Avanza 2016 Rp 135.000.000"),
            (None, None),
        )


class ParseListingPriceTests(unittest.TestCase):
    def test_parses_a_single_rupiah_price_from_text(self):
        self.assertEqual(
            parse_listing_price("Harga mobil Rp 165.000.000"),
            165_000_000,
        )

    def test_rejects_concatenated_prices(self):
        self.assertIsNone(
            parse_listing_price("Rp 165.000.000250.000.000422.500.000")
        )

    def test_rejects_values_outside_postgres_bigint_range(self):
        self.assertIsNone(parse_listing_price("9223372036854775808"))


class ExtractListingMetadataTests(unittest.TestCase):
    def test_extracts_schema_mileage_price_and_seller_location(self):
        records = extract_vehicle_schema_listings(
            [
                {
                    "@type": ["Car", "Product"],
                    "name": "2017 Honda Brio 1.2 RS",
                    "mainEntityOfPage": "https://example.com/listing/1",
                    "mileageFromOdometer": {
                        "@type": "QuantitativeValue",
                        "unitCode": "KMT",
                        "value": 42_500,
                    },
                    "offers": {
                        "price": 93_500_000,
                        "seller": {
                            "address": {
                                "addressLocality": "Kemayoran",
                                "addressRegion": "DKI Jakarta",
                            }
                        },
                    },
                }
            ],
            "Mobil123",
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mileage_min_km"], 42_500)
        self.assertEqual(records[0]["mileage_max_km"], 42_500)
        self.assertEqual(records[0]["location"], "Kemayoran, DKI Jakarta")
        self.assertEqual(records[0]["price"], 93_500_000)

    def test_falls_back_to_listing_text_when_schema_mileage_is_zero(self):
        records = extract_vehicle_schema_listings(
            {
                "@type": "Product",
                "name": "2017 Honda Brio Kilometer 40 ribu",
                "url": "https://example.com/listing/2",
                "mileageFromOdometer": {"value": 0},
                "offers": {"price": 95_000_000},
            },
            "Carmudi",
        )

        self.assertEqual(records[0]["mileage_min_km"], 40_000)
        self.assertEqual(records[0]["mileage_max_km"], 40_000)

    def test_extracts_location_only_from_location_marked_card_element(self):
        card = BeautifulSoup(
            '<div><span data-testid="location">Jakarta Selatan</span></div>',
            "html.parser",
        ).div

        self.assertEqual(extract_card_location(card), "Jakarta Selatan")


if __name__ == "__main__":
    unittest.main()
