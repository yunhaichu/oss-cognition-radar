import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import radar  # noqa: E402


def selector_payload(validation_fixtures):
    return {
        "schema_version": "route_detail_selectors_v1",
        "db": "test.sqlite",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "scope": "latest_deep_dossiers",
        "filters": {
            "track": None,
            "min_track_score": 0,
            "signal_group": None,
            "profile_path_confidence_source": None,
            "profile_path_move": None,
            "profile_path_route": None,
            "profile_path_repo": None,
            "validation_fixture_status": validation_fixtures.get("fixture_status_filter"),
        },
        "summary": {
            "move_count": 1,
            "route_count": 1,
            "example_count": 2,
            "repository_count": 1,
            "unique_evidence_count": 1,
            "preset_count": 1,
        },
        "moves": [
            {
                "comparison_id": "cmp_1",
                "move_key": "boundary_design::Architecture boundary",
                "design_move": "Architecture boundary",
                "selector_values": ["cmp_1", "boundary_design::Architecture boundary"],
                "comparison_confidence": "high",
                "comparison_score": 86,
                "repository_count": 1,
                "route_count": 1,
                "example_count": 2,
                "routes": [
                    {
                        "route_id": "validation::tests",
                        "route_label": "Validation / tests",
                        "selector_values": ["validation::tests", "tests"],
                        "repository_count": 1,
                        "example_count": 2,
                        "high_confidence_examples": 1,
                        "average_confidence": 82,
                        "repository_options": [{"value": "owner/repo", "count": 2}],
                        "confidence_sources": [{"value": "auto", "count": 1}],
                        "signal_groups": [{"value": "evidence", "count": 1}],
                    }
                ],
            }
        ],
        "preset_bundle": {
            "schema_version": "route_detail_selector_preset_bundle_v1",
            "preset_count": 1,
            "presets": [
                {
                    "preset_id": "preset_1",
                    "label": "Preset 1",
                    "selectors": {
                        "profile_path_move": "boundary_design::Architecture boundary",
                        "profile_path_route": "validation::tests",
                        "profile_path_repo": "owner/repo",
                    },
                }
            ],
        },
        "validation_fixtures": validation_fixtures,
    }


def validation_fixtures(status_filter, fixtures, status_counts, matching_expected):
    return {
        "schema_version": "route_detail_preset_validation_fixtures_v1",
        "source": "archive_route_selectors",
        "fixture_status_filter": status_filter,
        "fixture_count": len(fixtures),
        "unfiltered_fixture_count": 4,
        "matching_expected_count": matching_expected,
        "unfiltered_matching_expected_count": 4,
        "fixture_status_counts": status_counts,
        "all_fixture_status_counts": {"blocked": 3, "duplicate_ids": 1},
        "fixtures": fixtures,
    }


def fixture(fixture_id, validation_status, expected_status):
    return {
        "fixture_id": fixture_id,
        "expected_validation_status": expected_status,
        "validation_status": validation_status,
        "validation_matches_expected": validation_status == expected_status,
        "description": f"{fixture_id} fixture",
        "validation_summary": {
            "status": validation_status,
            "ready_preset_count": 0,
            "unmatched_preset_count": 1,
        },
    }


class RouteSelectorProvenanceMarkdownTest(unittest.TestCase):
    def render(self, validation_fixture_payload):
        return radar.render_archive_route_selectors(selector_payload(validation_fixture_payload))

    def test_blocked_filter_renders_filtered_and_unfiltered_provenance(self):
        markdown = self.render(
            validation_fixtures(
                "blocked",
                [
                    fixture("missing_move", "blocked", "blocked"),
                    fixture("missing_route", "blocked", "blocked"),
                    fixture("missing_repo", "blocked", "blocked"),
                ],
                {"blocked": 3},
                3,
            )
        )

        self.assertIn("Source", markdown)
        self.assertIn("archive_route_selectors", markdown)
        self.assertIn("Fixture status filter", markdown)
        self.assertIn("blocked", markdown)
        self.assertIn("Fixture count / unfiltered", markdown)
        self.assertIn("3 / 4", markdown)
        self.assertIn("Matching expected / unfiltered", markdown)
        self.assertIn("Status counts", markdown)
        self.assertIn("blocked=3", markdown)
        self.assertIn("All status counts", markdown)
        self.assertIn("duplicate_ids=1", markdown)

    def test_duplicate_ids_filter_renders_single_fixture_provenance(self):
        markdown = self.render(
            validation_fixtures(
                "duplicate_ids",
                [fixture("duplicate_ids", "duplicate_ids", "duplicate_ids")],
                {"duplicate_ids": 1},
                1,
            )
        )

        self.assertIn("Fixture status filter", markdown)
        self.assertIn("duplicate_ids", markdown)
        self.assertIn("Fixture count / unfiltered", markdown)
        self.assertIn("1 / 4", markdown)
        self.assertIn("Matching expected / unfiltered", markdown)
        self.assertIn("Status counts", markdown)
        self.assertIn("duplicate_ids=1", markdown)
        self.assertIn("All status counts", markdown)
        self.assertIn("blocked=3, duplicate_ids=1", markdown)

    def test_ready_filter_renders_empty_scope_with_all_status_counts(self):
        markdown = self.render(validation_fixtures("ready", [], {}, 0))

        self.assertIn("Fixture status filter", markdown)
        self.assertIn("ready", markdown)
        self.assertIn("Fixture count / unfiltered", markdown)
        self.assertIn("0 / 4", markdown)
        self.assertIn("Matching expected / unfiltered", markdown)
        self.assertIn("Status counts", markdown)
        self.assertIn("All status counts", markdown)
        self.assertIn("blocked=3, duplicate_ids=1", markdown)
        self.assertIn("validation fixtures", markdown)


if __name__ == "__main__":
    unittest.main()
