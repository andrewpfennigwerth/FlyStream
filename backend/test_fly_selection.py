import unittest
from unittest.mock import patch

from agent import (
    DEFAULT_QUOTAS,
    build_fly_catalog,
    enforce_type_diversity,
    extract_fly_names_from_reports,
    flatten_grouped_flies,
    group_top_flies_by_type,
    pattern_matches_region,
    prioritize_fly_patterns,
    recommend_flies,
    select_fly_box_with_quotas,
    unique_fly_patterns,
)


SYNTHETIC_CATALOG = [
    {"fly_name": "Parachute Adams", "type": "dry", "regions": '["northeast"]'},
    {"fly_name": "Elk Hair Caddis", "type": "dry", "regions": '["northeast"]'},
    {"fly_name": "Blue-Winged Olive (BWO)", "type": "dry", "regions": '["northeast"]'},
    {"fly_name": "Stimulator", "type": "dry", "regions": '["western_us"]'},
    {"fly_name": "Pheasant Tail Nymph", "type": "nymph", "regions": '["northeast"]'},
    {"fly_name": "Hare's Ear Nymph", "type": "nymph", "regions": '["northeast"]'},
    {"fly_name": "Zebra Midge", "type": "nymph", "regions": '["northeast"]'},
    {"fly_name": "Prince Nymph", "type": "nymph", "regions": '["western_us"]'},
    {"fly_name": "Woolly Bugger", "type": "streamer", "regions": '["northeast"]'},
    {"fly_name": "Grey Ghost", "type": "streamer", "regions": '["northeast"]'},
    {"fly_name": "Mickey Finn", "type": "streamer", "regions": '["northeast"]'},
    {"fly_name": "Clouser Minnow", "type": "streamer", "regions": '["western_us"]'},
    {"fly_name": "Egg Pattern", "type": "junk", "regions": '["northeast"]'},
    {"fly_name": "San Juan Worm", "type": "junk", "regions": '["northeast"]'},
    {"fly_name": "Mop Fly", "type": "junk", "regions": '["northeast"]'},
]


def _filtered_search(catalog):
    """Return a side-effect that honors `type_filter` for search_fly_patterns mocks."""

    def _side_effect(query, k=3, type_filter=None):
        items = [
            p for p in catalog
            if type_filter is None or p.get("type") == type_filter
        ]
        return items[:k]

    return _side_effect


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

    def test_group_top_flies_by_type_limits_to_three(self):
        patterns = [
            {"fly_name": "A", "type": "dry"},
            {"fly_name": "B", "type": "dry"},
            {"fly_name": "C", "type": "dry"},
            {"fly_name": "D", "type": "dry"},
            {"fly_name": "E", "type": "nymph"},
        ]
        grouped = group_top_flies_by_type(patterns, top_n_per_type=3)
        self.assertEqual(len(grouped["dry"]), 3)
        self.assertEqual([f["fly_name"] for f in grouped["dry"]], ["A", "B", "C"])
        self.assertEqual([f["fly_name"] for f in grouped["nymph"]], ["E"])

    def test_flatten_grouped_flies_has_no_duplicates_when_input_unique(self):
        grouped = {
            "dry": [{"fly_name": "Parachute Adams", "type": "dry"}],
            "nymph": [{"fly_name": "Zebra Midge", "type": "nymph"}],
            "streamer": [{"fly_name": "Woolly Bugger", "type": "streamer"}],
        }
        flattened = flatten_grouped_flies(grouped)
        names = [f["fly_name"] for f in flattened]
        self.assertEqual(len(names), len(set(names)))

    def test_pattern_matches_region_handles_json_and_list(self):
        json_pattern = {"regions": '["northeast", "midwest"]'}
        list_pattern = {"regions": ["rocky_mountains"]}
        self.assertTrue(pattern_matches_region(json_pattern, ["northeast"]))
        self.assertFalse(pattern_matches_region(json_pattern, ["western_us"]))
        self.assertTrue(pattern_matches_region(list_pattern, ["rocky_mountains"]))
        self.assertFalse(pattern_matches_region({}, ["northeast"]))

    def test_quota_selection_meets_default_quotas(self):
        picked = select_fly_box_with_quotas(
            base_query="test",
            report_fly_mentions=[],
            region_tags=["northeast"],
            search_fn=_filtered_search(SYNTHETIC_CATALOG),
        )
        self.assertEqual(len(picked), sum(DEFAULT_QUOTAS.values()))
        type_counts = {}
        for pattern in picked:
            type_counts[pattern["type"]] = type_counts.get(pattern["type"], 0) + 1
        self.assertEqual(type_counts.get("dry"), DEFAULT_QUOTAS["dry"])
        self.assertEqual(type_counts.get("nymph"), DEFAULT_QUOTAS["nymph"])
        self.assertEqual(type_counts.get("streamer"), DEFAULT_QUOTAS["streamer"])
        self.assertEqual(type_counts.get("junk"), DEFAULT_QUOTAS["junk"])

    def test_region_preference_promotes_region_tagged_fly(self):
        catalog = [
            {"fly_name": "Generic Dry", "type": "dry", "regions": '["western_us"]'},
            {"fly_name": "Local Dry", "type": "dry", "regions": '["northeast"]'},
        ]
        picked = select_fly_box_with_quotas(
            base_query="test",
            report_fly_mentions=[],
            region_tags=["northeast"],
            quotas={"dry": 1},
            search_fn=_filtered_search(catalog),
        )
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0]["fly_name"], "Local Dry")

    def test_quota_selection_promotes_report_mentions_over_region(self):
        catalog = [
            {"fly_name": "Region Dry", "type": "dry", "regions": '["northeast"]'},
            {"fly_name": "Mentioned Dry", "type": "dry", "regions": '["western_us"]'},
        ]
        picked = select_fly_box_with_quotas(
            base_query="test",
            report_fly_mentions=["Mentioned Dry"],
            region_tags=["northeast"],
            quotas={"dry": 1},
            search_fn=_filtered_search(catalog),
        )
        self.assertEqual(picked[0]["fly_name"], "Mentioned Dry")

    @patch("agent.search_fishing_report")
    @patch("agent.search_fly_patterns")
    @patch("agent.verify_and_rerank_with_llm")
    def test_recommend_flies_fallback_when_verification_fails(
        self, mock_verify, mock_search_patterns, mock_search_report
    ):
        mock_search_report.invoke.return_value = "Title: Report\nContent: bwo and pt\n---"
        mock_search_patterns.side_effect = _filtered_search(SYNTHETIC_CATALOG)
        mock_verify.side_effect = RuntimeError("verification unavailable")

        result = recommend_flies("Bozeman, MT", use_llm_verification=True)
        self.assertIn("flies_by_type", result)
        self.assertFalse(result["verification"]["used_llm"])
        self.assertTrue(result["verification"]["fallback_used"])

        max_per_type = max(DEFAULT_QUOTAS.values())
        for _, flies in result["flies_by_type"].items():
            self.assertLessEqual(len(flies), max_per_type)

        self.assertEqual(len(result["fly_box"]), sum(DEFAULT_QUOTAS.values()))

    @patch("agent.search_fishing_report")
    @patch("agent.search_fly_patterns")
    def test_recommend_flies_is_deterministic_without_llm(
        self, mock_search_patterns, mock_search_report
    ):
        mock_search_report.invoke.return_value = "Title: Report\nContent: zebra midge bwo\n---"
        mock_search_patterns.side_effect = _filtered_search(SYNTHETIC_CATALOG)

        result_one = recommend_flies("Bozeman, MT", use_llm_verification=False)
        mock_search_patterns.side_effect = _filtered_search(SYNTHETIC_CATALOG)
        result_two = recommend_flies("Bozeman, MT", use_llm_verification=False)
        self.assertEqual(result_one["flies_by_type"], result_two["flies_by_type"])
        self.assertEqual(result_one["fly_box"], result_two["fly_box"])

    @patch("agent.search_fly_patterns")
    def test_enforce_type_diversity_backfills_missing_types(self, mock_search_patterns):
        base_ranked = [
            {"fly_name": "Grey Ghost", "type": "streamer"},
            {"fly_name": "Mickey Finn", "type": "streamer"},
            {"fly_name": "Trout Slayer", "type": "streamer"},
        ]

        def side_effect(query, k=3, type_filter=None):
            if "dry" in query:
                return [{"fly_name": "Parachute Adams", "type": "dry"}]
            if "nymph" in query:
                return [{"fly_name": "Zebra Midge", "type": "nymph"}]
            if "junk" in query:
                return [{"fly_name": "Egg Pattern", "type": "junk"}]
            return []

        mock_search_patterns.side_effect = side_effect
        diverse = enforce_type_diversity(base_ranked, base_query="test", top_n_per_type=1)
        grouped = group_top_flies_by_type(diverse, top_n_per_type=1)

        self.assertIn("streamer", grouped)
        self.assertIn("dry", grouped)
        self.assertIn("nymph", grouped)
        self.assertIn("junk", grouped)
        all_names = [p["fly_name"] for p in diverse]
        self.assertNotIn("Trout Slayer", all_names)


if __name__ == "__main__":
    unittest.main()
