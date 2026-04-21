import unittest

from agent import (
    build_fly_catalog,
    extract_fly_names_from_reports,
    prioritize_fly_patterns,
    unique_fly_patterns,
)


class FlySelectionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = build_fly_catalog()

    def test_alias_extraction_maps_to_canonical_names(self):
        reports = [
            "Cloudy day with strong bwo hatch. PT and zebra midge produced fish.",
            "Wooly bugger stripped through deep runs worked late.",
        ]
        extracted = extract_fly_names_from_reports(reports, self.catalog)
        self.assertIn("Blue-Winged Olive (BWO)", extracted)
        self.assertIn("Pheasant Tail Nymph", extracted)
        self.assertIn("Zebra Midge", extracted)
        self.assertIn("Woolly Bugger", extracted)

    def test_extractor_ignores_generic_report_words(self):
        reports = [
            "Title: Weekly Report. Source: Example Outfitters.",
            "Great conditions with clear skies and moderate flows.",
        ]
        extracted = extract_fly_names_from_reports(reports, self.catalog)
        self.assertEqual(extracted, [])

    def test_unique_fly_patterns_removes_duplicates(self):
        patterns = [
            {"fly_name": "Woolly Bugger", "type": "streamer"},
            {"fly_name": "Woolly Bugger", "type": "streamer"},
            {"fly_name": "Zebra Midge", "type": "nymph"},
        ]
        deduped = unique_fly_patterns(patterns)
        self.assertEqual([p["fly_name"] for p in deduped], ["Woolly Bugger", "Zebra Midge"])

    def test_prioritize_fly_patterns_promotes_report_mentions(self):
        patterns = [
            {"fly_name": "Woolly Bugger", "type": "streamer"},
            {"fly_name": "Zebra Midge", "type": "nymph"},
            {"fly_name": "Parachute Adams", "type": "dry"},
        ]
        prioritized = prioritize_fly_patterns(patterns, ["Zebra Midge"])
        self.assertEqual(prioritized[0]["fly_name"], "Zebra Midge")


if __name__ == "__main__":
    unittest.main()
