import argparse
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import radar  # noqa: E402


def args_for_fixture(fixture_id=None, preset_ids=None):
    return argparse.Namespace(
        profile_path_preset_fixture=fixture_id,
        profile_path_preset_id=preset_ids or [],
    )


def preset(preset_id="preset_1"):
    return {
        "preset_id": preset_id,
        "label": "Preset 1",
        "selectors": {
            "profile_path_move": "boundary_design::Architecture boundary",
            "profile_path_route": "validation::tests",
            "profile_path_repo": "owner/repo",
        },
    }


def selector_fixture_payload():
    return {
        "schema_version": "route_detail_selectors_v1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "filters": {
            "validation_fixture_status": "blocked",
            "profile_path_move": "boundary_design::Architecture boundary",
        },
        "validation_fixtures": {
            "schema_version": "route_detail_preset_validation_fixtures_v1",
            "source": "archive_route_selectors",
            "fixture_status_filter": "blocked",
            "fixture_count": 3,
            "unfiltered_fixture_count": 4,
            "matching_expected_count": 3,
            "unfiltered_matching_expected_count": 4,
            "fixture_status_counts": {"blocked": 3},
            "all_fixture_status_counts": {"blocked": 3, "duplicate_ids": 1},
            "fixtures": [
                {
                    "fixture_id": "missing_move",
                    "description": "Missing move fixture",
                    "expected_validation_status": "blocked",
                    "validation_status": "blocked",
                    "validation_matches_expected": True,
                    "preset_bundle": {
                        "schema_version": "route_detail_selector_preset_bundle_v1",
                        "generated_at": "2026-05-27T00:00:00+00:00",
                        "source": "archive_route_selectors",
                        "preset_count": 1,
                        "presets": [preset()],
                    },
                }
            ],
        },
    }


def dashboard_fixture_bundle():
    return {
        "schema_version": "route_detail_selector_preset_bundle_v1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "source": "dashboard_route_detail_validation_fixture",
        "fixture_id": "duplicate_ids",
        "fixture_description": "Duplicate ID fixture",
        "expected_validation_status": "duplicate_ids",
        "source_selector_filters": {"fixture_validation_status": "duplicate_ids"},
        "source_fixture_status_filter": "duplicate_ids",
        "source_fixture_count": 1,
        "source_unfiltered_fixture_count": 4,
        "source_fixture_matching_expected_count": 1,
        "source_fixture_unfiltered_matching_expected_count": 4,
        "source_fixture_status_counts": {"duplicate_ids": 1},
        "source_all_fixture_status_counts": {"blocked": 3, "duplicate_ids": 1},
        "validation_status": "duplicate_ids",
        "validation_matches_expected": True,
        "preset_count": 2,
        "presets": [preset("duplicate"), preset("duplicate")],
    }


def preset_exports_payload(bundle):
    return {
        "schema_version": "route_detail_preset_exports_v1",
        "db": "test.sqlite",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "source_preset_path": "fixture.json",
        "source_bundle_schema": bundle.get("schema_version"),
        "source_fixture_id": bundle.get("fixture_id"),
        "source_fixture_description": bundle.get("fixture_description"),
        "source_selector_filters": bundle.get("source_selector_filters") or {},
        "source_fixture_status_filter": bundle.get("source_fixture_status_filter"),
        "source_fixture_count": bundle.get("source_fixture_count"),
        "source_unfiltered_fixture_count": bundle.get("source_unfiltered_fixture_count"),
        "source_fixture_matching_expected_count": bundle.get("source_fixture_matching_expected_count"),
        "source_fixture_unfiltered_matching_expected_count": bundle.get(
            "source_fixture_unfiltered_matching_expected_count"
        ),
        "source_fixture_status_counts": bundle.get("source_fixture_status_counts") or {},
        "source_all_fixture_status_counts": bundle.get("source_all_fixture_status_counts") or {},
        "source_fixture_validation_status": bundle.get("validation_status"),
        "source_fixture_validation_matches_expected": bundle.get("validation_matches_expected"),
        "expected_validation_status": bundle.get("expected_validation_status"),
        "preset_validation": {
            "schema_version": "route_detail_preset_validation_v1",
            "status": bundle.get("validation_status"),
            "source_bundle_preset_count": bundle.get("preset_count"),
            "selected_preset_count": len(bundle.get("presets") or []),
            "ready_preset_count": 0,
            "unmatched_preset_count": len(bundle.get("presets") or []),
            "expected_route_count": 0,
            "expected_example_count": 0,
            "duplicate_preset_ids": ["duplicate"] if bundle.get("validation_status") == "duplicate_ids" else [],
            "preset_statuses": [],
        },
        "summary": {
            "preset_count": len(bundle.get("presets") or []),
            "route_count": 0,
            "example_count": 0,
            "repository_count": 0,
            "unique_evidence_count": 0,
        },
        "exports": [],
    }


class RouteDetailPresetProvenanceRoundtripTest(unittest.TestCase):
    def assert_common_markdown(self, markdown, status_filter, fixture_count, matching_count, status_counts):
        self.assertIn("Source fixture status filter", markdown)
        self.assertIn(status_filter, markdown)
        self.assertIn("Source selector fixture filter", markdown)
        self.assertIn("Source fixture count", markdown)
        self.assertIn(f"{fixture_count} / unfiltered 4", markdown)
        self.assertIn("Source fixture matching expected", markdown)
        self.assertIn(f"{matching_count} / unfiltered 4", markdown)
        self.assertIn("Source fixture status counts", markdown)
        self.assertIn(status_counts, markdown)
        self.assertIn("Source all fixture status counts", markdown)
        self.assertIn("blocked=3, duplicate_ids=1", markdown)

    def test_selector_fixture_roundtrip_preserves_source_provenance(self):
        bundle = radar.route_detail_preset_bundle_from_payload(
            selector_fixture_payload(), args_for_fixture("missing_move")
        )

        self.assertEqual(bundle["fixture_id"], "missing_move")
        self.assertEqual(bundle["source_selector_filters"]["validation_fixture_status"], "blocked")
        self.assertEqual(bundle["source_fixture_status_filter"], "blocked")
        self.assertEqual(bundle["source_fixture_count"], 3)
        self.assertEqual(bundle["source_unfiltered_fixture_count"], 4)
        self.assertEqual(bundle["source_fixture_matching_expected_count"], 3)
        self.assertEqual(bundle["source_fixture_status_counts"], {"blocked": 3})
        self.assertEqual(bundle["source_all_fixture_status_counts"], {"blocked": 3, "duplicate_ids": 1})
        self.assertEqual(bundle["validation_status"], "blocked")
        self.assertIs(bundle["validation_matches_expected"], True)

        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload(bundle))
        self.assertIn("Source fixture", markdown)
        self.assertIn("missing_move", markdown)
        self.assertIn("Source selector fixture filter", markdown)
        self.assertIn("blocked", markdown)
        self.assertIn("Source fixture validation", markdown)
        self.assertIn("matches expected True", markdown)
        self.assert_common_markdown(markdown, "blocked", 3, 3, "blocked=3")

    def test_dashboard_single_fixture_bundle_roundtrip_preserves_source_provenance(self):
        bundle = radar.route_detail_preset_bundle_from_payload(
            dashboard_fixture_bundle(), args_for_fixture()
        )

        self.assertEqual(bundle["source"], "dashboard_route_detail_validation_fixture")
        self.assertEqual(bundle["fixture_id"], "duplicate_ids")
        self.assertEqual(bundle["source_selector_filters"]["fixture_validation_status"], "duplicate_ids")
        self.assertEqual(bundle["source_fixture_status_filter"], "duplicate_ids")
        self.assertEqual(bundle["source_fixture_count"], 1)
        self.assertEqual(bundle["source_unfiltered_fixture_count"], 4)
        self.assertEqual(bundle["source_fixture_matching_expected_count"], 1)
        self.assertEqual(bundle["source_fixture_status_counts"], {"duplicate_ids": 1})
        self.assertEqual(bundle["source_all_fixture_status_counts"], {"blocked": 3, "duplicate_ids": 1})
        self.assertEqual(bundle["validation_status"], "duplicate_ids")
        self.assertIs(bundle["validation_matches_expected"], True)

        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload(bundle))
        self.assertIn("Source fixture", markdown)
        self.assertIn("duplicate_ids", markdown)
        self.assertIn("Expected validation status", markdown)
        self.assertIn("duplicate_ids", markdown)
        self.assertIn("Duplicate preset IDs", markdown)
        self.assertIn("duplicate", markdown)
        self.assert_common_markdown(markdown, "duplicate_ids", 1, 1, "duplicate_ids=1")

    def test_missing_fixture_id_reports_available_fixture_ids(self):
        with self.assertRaises(SystemExit) as raised:
            radar.route_detail_preset_bundle_from_payload(
                selector_fixture_payload(), args_for_fixture("missing_fixture")
            )

        message = str(raised.exception)
        self.assertIn("Preset validation fixture not found", message)
        self.assertIn("missing_fixture", message)
        self.assertIn("Available fixtures: missing_move", message)

    def test_preset_id_selection_returns_only_requested_presets(self):
        bundle = {
            "presets": [
                preset("preset_a"),
                preset("preset_b"),
                preset("preset_c"),
            ]
        }

        selected = radar.selected_route_detail_presets(
            bundle, args_for_fixture(preset_ids=["preset_b", "preset_c"])
        )

        self.assertEqual([item["preset_id"] for item in selected], ["preset_b", "preset_c"])

    def test_missing_preset_id_reports_unknown_ids(self):
        bundle = {"presets": [preset("preset_a")]}

        with self.assertRaises(SystemExit) as raised:
            radar.selected_route_detail_presets(bundle, args_for_fixture(preset_ids=["preset_missing"]))

        message = str(raised.exception)
        self.assertIn("Preset ID not found", message)
        self.assertIn("preset_missing", message)


if __name__ == "__main__":
    unittest.main()
