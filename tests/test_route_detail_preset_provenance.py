import argparse
import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import radar  # noqa: E402


def args_for_fixture(fixture_id=None, preset_ids=None):
    return argparse.Namespace(
        profile_path_preset_fixture=fixture_id,
        profile_path_preset_id=preset_ids or [],
    )


def preset(preset_id="preset_1", repo="owner/repo"):
    return {
        "preset_id": preset_id,
        "label": f"Preset {preset_id}",
        "selectors": {
            "profile_path_move": "boundary_design::Architecture boundary",
            "profile_path_route": "validation::tests",
            "profile_path_repo": repo,
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


def dashboard_ready_fixture_bundle(source_filters=None):
    return {
        "schema_version": "route_detail_selector_preset_bundle_v1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "source": "dashboard_route_detail_validation_fixture",
        "fixture_id": "ready_dashboard",
        "fixture_description": "Ready dashboard fixture",
        "expected_validation_status": "ready",
        "source_selector_filters": source_filters or {"fixture_validation_status": "ready"},
        "source_fixture_status_filter": "ready",
        "source_fixture_count": 1,
        "source_unfiltered_fixture_count": 4,
        "source_fixture_matching_expected_count": 1,
        "source_fixture_unfiltered_matching_expected_count": 4,
        "source_fixture_status_counts": {"ready": 1},
        "source_all_fixture_status_counts": {"blocked": 1, "duplicate_ids": 1, "ready": 2},
        "validation_status": "ready",
        "validation_matches_expected": True,
        "preset_count": 1,
        "presets": [preset("dashboard_ready", "owner/repo")],
    }


def fixture_batch_selector_payload(extra_unselected_preset=False, source_filters=None):
    fixture_presets = [
        preset("batch_repo", "owner/repo"),
        preset("batch_second", "owner/second"),
    ]
    if extra_unselected_preset:
        fixture_presets.append(preset("batch_unselected", "owner/missing"))
    return {
        "schema_version": "route_detail_selectors_v1",
        "generated_at": "2026-05-27T00:00:00+00:00",
        "filters": source_filters or {"validation_fixture_status": "ready"},
        "summary": {
            "move_count": 1,
            "route_count": 1,
            "example_count": 3,
            "repository_count": 2,
            "unique_evidence_count": 2,
            "preset_count": 2,
        },
        "moves": [
            {
                "comparison_id": "cmp_1",
                "move_key": "boundary_design::Architecture boundary",
                "design_move_category": "boundary_design",
                "design_move": "Architecture boundary",
                "selector_values": ["cmp_1", "boundary_design::Architecture boundary", "Architecture boundary"],
                "routes": [
                    {
                        "route_id": "validation::tests",
                        "route_key": "validation::tests",
                        "route_label": "Validation / tests",
                        "claim_gap_layer": "validation",
                        "evidence_type": "tests",
                        "selector_values": ["validation::tests", "Validation / tests", "tests"],
                        "repository_count": 2,
                        "example_count": 3,
                        "repositories": ["owner/repo", "owner/second"],
                        "repository_options": [
                            {"value": "owner/repo", "count": 2},
                            {"value": "owner/second", "count": 1},
                        ],
                    }
                ],
            }
        ],
        "validation_fixtures": {
            "schema_version": "route_detail_preset_validation_fixtures_v1",
            "source": "archive_route_selectors",
            "fixture_status_filter": "ready",
            "fixture_count": 2,
            "unfiltered_fixture_count": 4,
            "matching_expected_count": 2,
            "unfiltered_matching_expected_count": 4,
            "fixture_status_counts": {"ready": 2},
            "all_fixture_status_counts": {"blocked": 1, "duplicate_ids": 1, "ready": 2},
            "fixtures": [
                {
                    "fixture_id": "ready_batch",
                    "description": "Ready fixture-driven batch",
                    "expected_validation_status": "ready",
                    "validation_status": "ready",
                    "validation_matches_expected": True,
                    "preset_bundle": {
                        "schema_version": "route_detail_selector_preset_bundle_v1",
                        "generated_at": "2026-05-27T00:00:00+00:00",
                        "source": "archive_route_selectors",
                        "preset_count": len(fixture_presets),
                        "presets": fixture_presets,
                    },
                }
            ],
        },
    }


def preset_export_args(fixture_id="ready_batch", preset_ids=None):
    args = args_for_fixture(fixture_id, preset_ids)
    args.profile_path_preset = "selectors.json"
    args.db = "test.sqlite"
    args.profile_path_move = None
    args.profile_path_route = None
    args.profile_path_repo = None
    args.profile_path_confidence_source = None
    args.archive_signal_group = None
    args.archive_track = None
    args.min_track_score = 0
    args.limit = 20
    return args


def fake_route_detail_payload(args):
    repo = args.profile_path_repo
    evidence_id = "ev_repo" if repo == "owner/repo" else "ev_second"
    return {
        "schema_version": "route_detail_drilldown_v1",
        "summary": {
            "route_count": 1,
            "example_count": 2 if repo == "owner/repo" else 1,
            "repository_count": 1,
            "unique_evidence_count": 1,
        },
        "routes": [
            {
                "route_id": args.profile_path_route,
                "repositories": [repo],
                "examples": [
                    {
                        "repo_full_name": repo,
                        "evidence_stable_id": evidence_id,
                    }
                ],
            }
        ],
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

    def test_preset_export_markdown_renders_malformed_root_payload_as_empty(self):
        markdown = radar.render_archive_route_detail_preset_exports(["bad payload"])
        lines = markdown.splitlines()

        self.assertIn("- Schema\uff1aroute_detail_preset_exports_v1", lines)
        self.assertIn("- Preset / route / example\uff1a0 / 0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertIn("\u5f53\u524d preset \u8303\u56f4\u6ca1\u6709\u53ef\u5bfc\u51fa\u7684 route detail\u3002", lines)
        self.assertFalse(any("bad payload" in line for line in lines))

    def test_preset_export_markdown_renders_empty_payload_baseline(self):
        markdown = radar.render_archive_route_detail_preset_exports({})
        lines = markdown.splitlines()

        self.assertIn("- Schema\uff1aroute_detail_preset_exports_v1", lines)
        self.assertIn("- \u6570\u636e\u5e93\uff1aunknown", lines)
        self.assertIn("- \u751f\u6210\u65f6\u95f4\uff1aunknown", lines)
        self.assertIn("- Preset source\uff1a\u65e0", lines)
        self.assertIn("- Requested preset IDs\uff1a\u65e0", lines)
        self.assertIn("- Source schema\uff1aunknown", lines)
        self.assertIn("- Source fixture\uff1a\u65e0", lines)
        self.assertIn("- Source selector filters\uff1a\u65e0", lines)
        self.assertIn("- Source fixture validation\uff1aunknown / matches expected unknown", lines)
        self.assertIn("- Source fixture count\uff1aunknown / unfiltered unknown", lines)
        self.assertIn("- Expected validation status\uff1a\u65e0", lines)
        self.assertIn("- Preset / route / example\uff1a0 / 0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertNotIn("## Preset Validation", lines)
        self.assertIn("\u5f53\u524d preset \u8303\u56f4\u6ca1\u6709\u53ef\u5bfc\u51fa\u7684 route detail\u3002", lines)

    def test_preset_export_markdown_renders_string_duplicate_preset_id_as_single_id(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["duplicate_preset_ids"] = "duplicate"
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Duplicate preset IDs\uff1aduplicate", lines)
        self.assertNotIn("- Duplicate preset IDs\uff1ad, u, p, l, i, c, a, t, e", lines)

    def test_preset_export_markdown_filters_malformed_duplicate_preset_ids(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["duplicate_preset_ids"] = [
            "duplicate",
            {"bad": "id"},
            None,
            ["nested"],
            "duplicate_second",
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Duplicate preset IDs\uff1aduplicate, duplicate_second", lines)
        self.assertFalse(any("{'bad': 'id'}" in line for line in lines))
        self.assertFalse(any("['nested']" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_duplicate_preset_id_payload_as_empty(self):
        for duplicate_preset_ids in ({"bad": "id"}, 7):
            with self.subTest(duplicate_preset_ids=duplicate_preset_ids):
                payload = preset_exports_payload({})
                payload["preset_validation"]["duplicate_preset_ids"] = duplicate_preset_ids
                markdown = radar.render_archive_route_detail_preset_exports(payload)
                lines = markdown.splitlines()

                self.assertIn("- Duplicate preset IDs\uff1a\u65e0", lines)

    def test_preset_export_markdown_renders_empty_source_selector_filters(self):
        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload({}))
        lines = markdown.splitlines()

        self.assertIn("- Source selector fixture filter\uff1a\u65e0", lines)
        self.assertIn("- Source selector filters\uff1a\u65e0", lines)

    def test_preset_export_markdown_renders_malformed_source_selector_filter_payload_as_empty(self):
        for source_selector_filters in ("fixture_validation_status=ready", ["ready"], 7):
            with self.subTest(source_selector_filters=source_selector_filters):
                payload = preset_exports_payload({})
                payload["source_selector_filters"] = source_selector_filters
                markdown = radar.render_archive_route_detail_preset_exports(payload)
                lines = markdown.splitlines()

                self.assertIn("- Source selector fixture filter\uff1a\u65e0", lines)
                self.assertIn("- Source selector filters\uff1a\u65e0", lines)

    def test_preset_export_markdown_renders_malformed_source_schema_and_fixture_identity_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["source_preset_path"] = {"bad": "path"}
        payload["source_bundle_schema"] = ["bad_schema"]
        payload["source_fixture_id"] = {"bad": "fixture"}
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset source\uff1a\u65e0", lines)
        self.assertIn("- Source schema\uff1aunknown", lines)
        self.assertIn("- Source fixture\uff1a\u65e0", lines)
        self.assertFalse(any("{'bad': 'path'}" in line for line in lines))
        self.assertFalse(any("['bad_schema']" in line for line in lines))
        self.assertFalse(any("{'bad': 'fixture'}" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_top_level_identity_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["schema_version"] = {"bad": "schema"}
        payload["db"] = ["bad.sqlite"]
        payload["generated_at"] = {"bad": "time"}
        payload["expected_validation_status"] = ["ready"]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Schema\uff1aroute_detail_preset_exports_v1", lines)
        self.assertIn("- \u6570\u636e\u5e93\uff1aunknown", lines)
        self.assertIn("- \u751f\u6210\u65f6\u95f4\uff1aunknown", lines)
        self.assertIn("- Expected validation status\uff1a\u65e0", lines)
        self.assertFalse(any("{'bad': 'schema'}" in line for line in lines))
        self.assertFalse(any("['bad.sqlite']" in line for line in lines))
        self.assertFalse(any("{'bad': 'time'}" in line for line in lines))
        self.assertFalse(any("['ready']" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_validation_summary_identity_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["schema_version"] = {"bad": "schema"}
        payload["preset_validation"]["status"] = ["ready"]
        payload["preset_validation"]["source_bundle_preset_count"] = {"bad": "count"}
        payload["preset_validation"]["selected_preset_count"] = ["bad"]
        payload["preset_validation"]["ready_preset_count"] = {"bad": "ready"}
        payload["preset_validation"]["unmatched_preset_count"] = None
        payload["preset_validation"]["expected_route_count"] = {"bad": "route"}
        payload["preset_validation"]["expected_example_count"] = ["example"]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Schema\uff1aroute_detail_preset_validation_v1", lines)
        self.assertIn("- Status\uff1aunknown", lines)
        self.assertIn("- Source presets\uff1a0", lines)
        self.assertIn("- Selected / ready / unmatched\uff1a0 / 0 / 0", lines)
        self.assertIn("- Selected preset count consistency\uff1a0 / summary 0 / matches summary True", lines)
        self.assertIn("- Expected route / example\uff1a0 / 0", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 0 / summary 0 / matches summary True; example 0 / summary 0 / matches summary True",
            lines,
        )
        self.assertFalse(any("{'bad': 'schema'}" in line for line in lines))
        self.assertFalse(any("['ready']" in line for line in lines))
        self.assertFalse(any("{'bad': 'count'}" in line for line in lines))
        self.assertFalse(any("['bad']" in line for line in lines))
        self.assertFalse(any("{'bad': 'ready'}" in line for line in lines))
        self.assertFalse(any("{'bad': 'route'}" in line for line in lines))
        self.assertFalse(any("['example']" in line for line in lines))

    def test_preset_export_markdown_filters_malformed_source_selector_filter_entries(self):
        payload = preset_exports_payload({})
        payload["source_selector_filters"] = {
            "fixture_validation_status": "ready",
            "confidence_source": "auto",
            "min_score": 72,
            "bad_dict": {"bad": "filter"},
            "bad_list": ["bad"],
            "bad_none": None,
            7: "bad_key",
        }
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source selector fixture filter\uff1aready", lines)
        self.assertIn(
            "- Source selector filters\uff1aconfidence_source=auto, fixture_validation_status=ready, min_score=72",
            lines,
        )
        self.assertFalse(any("{'bad': 'filter'}" in line for line in lines))
        self.assertFalse(any("['bad']" in line for line in lines))
        self.assertFalse(any("7=bad_key" in line for line in lines))

    def test_preset_export_markdown_renders_scalar_source_selector_filters_stably(self):
        payload = preset_exports_payload({})
        payload["source_selector_filters"] = {
            "archive_track": "agent",
            "enabled": True,
            "fixture_validation_status": "ready",
            "min_track_score": 70.5,
        }
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source selector fixture filter\uff1aready", lines)
        self.assertIn(
            "- Source selector filters\uff1aarchive_track=agent, enabled=True, fixture_validation_status=ready, min_track_score=70.5",
            lines,
        )

    def test_preset_export_markdown_renders_empty_requested_preset_ids(self):
        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload({}))
        lines = markdown.splitlines()

        self.assertIn("- Requested preset IDs\uff1a\u65e0", lines)

    def test_preset_export_markdown_renders_requested_preset_ids(self):
        payload = preset_exports_payload({})
        payload["requested_preset_ids"] = ["batch_repo", "batch_second"]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Requested preset IDs\uff1abatch_repo, batch_second", lines)

    def test_preset_export_markdown_renders_string_requested_preset_id_as_single_id(self):
        payload = preset_exports_payload({})
        payload["requested_preset_ids"] = "batch_repo"
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Requested preset IDs\uff1abatch_repo", lines)
        self.assertNotIn("- Requested preset IDs\uff1ab, a, t, c, h, _, r, e, p, o", lines)

    def test_preset_export_markdown_filters_malformed_requested_preset_ids(self):
        payload = preset_exports_payload({})
        payload["requested_preset_ids"] = [
            "batch_repo",
            {"bad": "id"},
            None,
            ["nested"],
            "batch_second",
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Requested preset IDs\uff1abatch_repo, batch_second", lines)
        self.assertFalse(any("{'bad': 'id'}" in line for line in lines))
        self.assertFalse(any("['nested']" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_requested_preset_id_payload_as_empty(self):
        for requested_preset_ids in ({"bad": "id"}, 7):
            with self.subTest(requested_preset_ids=requested_preset_ids):
                payload = preset_exports_payload({})
                payload["requested_preset_ids"] = requested_preset_ids
                markdown = radar.render_archive_route_detail_preset_exports(payload)
                lines = markdown.splitlines()

                self.assertIn("- Requested preset IDs\uff1a\u65e0", lines)

    def test_preset_export_markdown_renders_selected_preset_count_consistency(self):
        payload = preset_exports_payload({"presets": [preset("batch_repo"), preset("batch_second")]})
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Selected preset count consistency\uff1a2 / summary 2 / matches summary True", lines)

    def test_preset_export_markdown_flags_selected_preset_count_mismatch(self):
        payload = preset_exports_payload({"presets": [preset("batch_repo"), preset("batch_second")]})
        payload["summary"]["preset_count"] = 1
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Selected preset count consistency\uff1a2 / summary 1 / matches summary False", lines)

    def test_preset_export_markdown_renders_expected_route_example_consistency(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["summary"]["route_count"] = 2
        payload["summary"]["example_count"] = 3
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Expected route/example consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )

    def test_preset_export_markdown_flags_expected_route_example_mismatch(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["summary"]["route_count"] = 1
        payload["summary"]["example_count"] = 4
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Expected route/example consistency\uff1aroute 2 / summary 1 / matches summary False; example 3 / summary 4 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_defaults_missing_validation_counts_to_zero(self):
        payload = preset_exports_payload({})
        payload["summary"] = {}
        payload["preset_validation"] = {
            "schema_version": "route_detail_preset_validation_v1",
            "status": "ready",
            "duplicate_preset_ids": [],
            "preset_statuses": [],
        }
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source presets\uff1a0", lines)
        self.assertIn("- Selected / ready / unmatched\uff1a0 / 0 / 0", lines)
        self.assertIn("- Selected preset count consistency\uff1a0 / summary 1 / matches summary False", lines)
        self.assertIn("- Expected route / example\uff1a0 / 0", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 0 / summary 1 / matches summary False; example 0 / summary 2 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_preserves_explicit_zero_validation_counts(self):
        payload = preset_exports_payload({})
        payload["summary"] = {}
        payload["preset_validation"] = {
            "schema_version": "route_detail_preset_validation_v1",
            "status": "ready",
            "source_bundle_preset_count": 0,
            "selected_preset_count": 0,
            "ready_preset_count": 0,
            "unmatched_preset_count": 0,
            "expected_route_count": 0,
            "expected_example_count": 0,
            "duplicate_preset_ids": [],
            "preset_statuses": [],
        }
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source presets\uff1a0", lines)
        self.assertIn("- Selected / ready / unmatched\uff1a0 / 0 / 0", lines)
        self.assertIn("- Selected preset count consistency\uff1a0 / summary 1 / matches summary False", lines)
        self.assertIn("- Expected route / example\uff1a0 / 0", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 0 / summary 1 / matches summary False; example 0 / summary 2 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_defaults_missing_validation_preset_status_counts_to_zero(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "messages": ["ready status"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 0\uff1broutes 0\uff1brepos 0\uff1bexamples 0\uff1bready status",
            lines,
        )

    def test_preset_export_markdown_preserves_explicit_zero_validation_preset_status_counts(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 0,
                "matched_route_count": 0,
                "matched_repository_count": 0,
                "expected_example_count": 0,
                "messages": ["zero status"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 0\uff1broutes 0\uff1brepos 0\uff1bexamples 0\uff1bzero status",
            lines,
        )

    def test_preset_export_markdown_renders_malformed_validation_preset_status_counts_as_zero(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": {"bad": "move"},
                "matched_route_count": ["route"],
                "matched_repository_count": None,
                "expected_example_count": {"bad": "example"},
                "messages": ["malformed counts"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 0\uff1broutes 0\uff1brepos 0\uff1bexamples 0\uff1bmalformed counts",
            lines,
        )
        self.assertFalse(any("{'bad': 'move'}" in line for line in lines))
        self.assertFalse(any("['route']" in line for line in lines))
        self.assertFalse(any("{'bad': 'example'}" in line for line in lines))

    def test_preset_export_markdown_defaults_missing_validation_preset_status_identity(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": ["identity fallback"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `` unknown\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bidentity fallback",
            lines,
        )

    def test_preset_export_markdown_renders_malformed_validation_preset_status_identity_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": {"bad": "preset"},
                "status": ["ready"],
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": ["malformed identity"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `` unknown\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bmalformed identity",
            lines,
        )
        self.assertFalse(any("{'bad': 'preset'}" in line for line in lines))
        self.assertFalse(any("['ready']" in line for line in lines))

    def test_preset_export_markdown_defaults_missing_validation_preset_status_messages_to_empty(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1b",
            lines,
        )

    def test_preset_export_markdown_preserves_empty_validation_preset_status_messages(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": [],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1b",
            lines,
        )

    def test_preset_export_markdown_joins_multiple_validation_preset_status_messages(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": ["first match", "second match"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bfirst match; second match",
            lines,
        )

    def test_preset_export_markdown_renders_string_validation_preset_status_message_as_single_message(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": "single message",
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bsingle message",
            lines,
        )
        self.assertNotIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bs; i; n; g; l; e;  ; m; e; s; s; a; g; e",
            lines,
        )

    def test_preset_export_markdown_filters_malformed_validation_preset_status_messages(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": ["first match", {"bad": "message"}, None, ["bad"], "second match"],
            },
            {
                "preset_id": "batch_second",
                "status": "blocked",
                "messages": {"bad": "message"},
            },
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bfirst match; second match",
            lines,
        )
        self.assertIn("- `batch_second` blocked\uff1amoves 0\uff1broutes 0\uff1brepos 0\uff1bexamples 0\uff1b", lines)
        self.assertFalse(any("{'bad': 'message'}" in line for line in lines))
        self.assertFalse(any("['bad']" in line for line in lines))

    def test_preset_export_markdown_truncates_validation_preset_statuses_after_twelve(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": f"preset_{index}",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 1,
                "matched_repository_count": 1,
                "expected_example_count": 1,
                "messages": [f"status {index}"],
            }
            for index in range(14)
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `preset_0` ready\uff1amoves 1\uff1broutes 1\uff1brepos 1\uff1bexamples 1\uff1bstatus 0",
            lines,
        )
        self.assertIn(
            "- `preset_11` ready\uff1amoves 1\uff1broutes 1\uff1brepos 1\uff1bexamples 1\uff1bstatus 11",
            lines,
        )
        self.assertNotIn(
            "- `preset_12` ready\uff1amoves 1\uff1broutes 1\uff1brepos 1\uff1bexamples 1\uff1bstatus 12",
            lines,
        )
        self.assertIn("- ... 2 more preset statuses in JSON", lines)

    def test_preset_export_markdown_does_not_truncate_twelve_validation_preset_statuses(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            {
                "preset_id": f"preset_{index}",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 1,
                "matched_repository_count": 1,
                "expected_example_count": 1,
                "messages": [f"status {index}"],
            }
            for index in range(12)
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `preset_11` ready\uff1amoves 1\uff1broutes 1\uff1brepos 1\uff1bexamples 1\uff1bstatus 11",
            lines,
        )
        self.assertNotIn("- ... 0 more preset statuses in JSON", lines)
        self.assertNotIn("- ... 1 more preset statuses in JSON", lines)

    def test_preset_export_markdown_renders_empty_validation_preset_status_list_without_rows(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = []
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("## Preset Validation", lines)
        self.assertEqual([line for line in lines if line.startswith("- `")], [])
        self.assertFalse(any("more preset statuses in JSON" in line for line in lines))

    def test_preset_export_markdown_renders_missing_validation_preset_status_list_without_rows(self):
        payload = preset_exports_payload({})
        payload["preset_validation"].pop("preset_statuses")
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("## Preset Validation", lines)
        self.assertEqual([line for line in lines if line.startswith("- `")], [])
        self.assertFalse(any("more preset statuses in JSON" in line for line in lines))

    def test_preset_export_markdown_renders_null_validation_preset_status_list_without_rows(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = None
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("## Preset Validation", lines)
        self.assertEqual([line for line in lines if line.startswith("- `")], [])
        self.assertFalse(any("more preset statuses in JSON" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_validation_preset_status_list_without_rows(self):
        for malformed_statuses in ("not-a-status-list", {"preset_id": "batch_repo"}):
            with self.subTest(malformed_statuses=malformed_statuses):
                payload = preset_exports_payload({})
                payload["preset_validation"]["preset_statuses"] = malformed_statuses
                markdown = radar.render_archive_route_detail_preset_exports(payload)
                lines = markdown.splitlines()

                self.assertIn("## Preset Validation", lines)
                self.assertEqual([line for line in lines if line.startswith("- `")], [])
                self.assertFalse(any("more preset statuses in JSON" in line for line in lines))

    def test_preset_export_markdown_skips_malformed_validation_preset_status_entries(self):
        payload = preset_exports_payload({})
        payload["preset_validation"]["preset_statuses"] = [
            "not-a-status",
            {
                "preset_id": "batch_repo",
                "status": "ready",
                "matched_move_count": 1,
                "matched_route_count": 2,
                "matched_repository_count": 3,
                "expected_example_count": 4,
                "messages": ["valid status"],
            },
            ["not", "a", "status"],
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- `batch_repo` ready\uff1amoves 1\uff1broutes 2\uff1brepos 3\uff1bexamples 4\uff1bvalid status",
            lines,
        )
        self.assertNotIn("- `` unknown\uff1amoves 0\uff1broutes 0\uff1brepos 0\uff1bexamples 0\uff1b", lines)
        self.assertFalse(any("more preset statuses in JSON" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_validation_payload_without_validation_section(self):
        payload = preset_exports_payload({})
        payload["preset_validation"] = ["bad validation"]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertNotIn("## Preset Validation", lines)
        self.assertFalse(any("bad validation" in line for line in lines))

    def test_preset_export_markdown_renders_repository_evidence_count_consistency(self):
        payload = preset_exports_payload({})
        payload["summary"]["repository_count"] = 2
        payload["summary"]["unique_evidence_count"] = 2
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second", "owner/repo"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_repo"},
                            ],
                        }
                    ]
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 2 / matches summary True",
            lines,
        )

    def test_preset_export_markdown_flags_repository_evidence_count_mismatch(self):
        payload = preset_exports_payload({})
        payload["summary"]["repository_count"] = 1
        payload["summary"]["unique_evidence_count"] = 3
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        }
                    ]
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 1 / matches summary False; evidence 2 / summary 3 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_renders_per_export_route_example_count_consistency(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "route_count": 2,
                        "example_count": 3,
                    },
                    "routes": [
                        {"examples": [{"evidence_stable_id": "ev_repo"}, {"evidence_id": "ev_second"}]},
                        {"examples": [{"evidence_stable_id": "ev_third"}]},
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )

    def test_preset_export_markdown_flags_per_export_route_example_count_mismatch(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "route_count": 1,
                        "example_count": 4,
                    },
                    "routes": [
                        {"examples": [{"evidence_stable_id": "ev_repo"}, {"evidence_id": "ev_second"}]},
                        {"examples": [{"evidence_stable_id": "ev_third"}]},
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 1 / matches summary False; example 3 / summary 4 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_renders_per_export_repository_evidence_count_consistency(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "repository_count": 2,
                        "unique_evidence_count": 2,
                    },
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second", "owner/repo"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_repo"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 2 / matches summary True",
            lines,
        )

    def test_preset_export_markdown_flags_per_export_repository_evidence_count_mismatch(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "repository_count": 1,
                        "unique_evidence_count": 3,
                    },
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 1 / matches summary False; evidence 2 / summary 3 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_renders_per_route_evidence_example_count_consistency(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "example_count": 3,
                            "unique_evidence_count": 2,
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_repo"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 3 / route 3 / matches route True; evidence 2 / route 2 / matches route True",
            lines,
        )

    def test_preset_export_markdown_filters_malformed_route_evidence_ids(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "unique_evidence_count": 2,
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_stable_id": {"bad": "stable"}, "evidence_id": ["bad_id"]},
                                {"evidence_stable_id": "", "evidence_id": "ev_second"},
                                {"evidence_id": {"bad": "id"}},
                                ["not an example"],
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("  - Evidence stable IDs\uff1aev_repo, ev_second", lines)
        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 4 / route 4 / matches route True; evidence 2 / route 2 / matches route True",
            lines,
        )
        self.assertIn("- Repository / unique evidence\uff1a0 / 2", lines)
        self.assertFalse(any("{'bad': 'stable'}" in line for line in lines))
        self.assertFalse(any("['bad_id']" in line for line in lines))
        self.assertFalse(any("{'bad': 'id'}" in line for line in lines))
        self.assertFalse(any("not an example" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_route_examples_payload_as_empty(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "examples": {"bad": "examples"},
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a1 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 0 / route 0 / matches route True; evidence 0 / route 0 / matches route True",
            lines,
        )
        self.assertIn("  - Evidence stable IDs\uff1a\u65e0", lines)
        self.assertFalse(any("{'bad': 'examples'}" in line for line in lines))

    def test_preset_export_markdown_filters_malformed_route_list_entries(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        "bad route",
                        {"bad": "route"},
                        {
                            "route_id": "validation::tests",
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a2 / 1", lines)
        self.assertIn("- Repository / unique evidence\uff1a1 / 1", lines)
        self.assertIn("- `` Design move / route", lines)
        self.assertIn("- `validation::tests` Design move / route", lines)
        self.assertFalse(any("bad route" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_route_list_payload_as_empty(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": {"bad": "routes"},
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertFalse(any("{'bad': 'routes'}" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_route_detail_payload_as_empty(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": ["bad route detail"],
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertFalse(any("bad route detail" in line for line in lines))

    def test_preset_export_markdown_filters_malformed_export_entries(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            "bad export",
            {"bad": "export"},
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        }
                    ],
                },
            },
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a0 / 0 / 0", lines)
        self.assertIn("## 1. Preset batch_repo", lines)
        self.assertIn("- Route / example\uff1a1 / 1", lines)
        self.assertIn("- Repository / unique evidence\uff1a1 / 1", lines)
        self.assertFalse(any("bad export" in line for line in lines))
        self.assertFalse(any("{'bad': 'export'}" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_exports_payload_as_empty(self):
        payload = preset_exports_payload({})
        payload["exports"] = {"bad": "exports"}
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a0 / 0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertIn("\u5f53\u524d preset \u8303\u56f4\u6ca1\u6709\u53ef\u5bfc\u51fa\u7684 route detail\u3002", lines)
        self.assertFalse(any("{'bad': 'exports'}" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_route_identity_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": {"bad": "route"},
                            "design_move": ["move"],
                            "route_label": {"bad": "label"},
                            "repositories": [],
                            "examples": [],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- `` Design move / route", lines)
        self.assertFalse(any("{'bad': 'route'}" in line for line in lines))
        self.assertFalse(any("['move']" in line for line in lines))
        self.assertFalse(any("{'bad': 'label'}" in line for line in lines))

    def test_preset_export_markdown_flags_per_route_evidence_example_count_mismatch(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "example_count": 4,
                            "unique_evidence_count": 1,
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_repo"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 3 / route 4 / matches route False; evidence 2 / route 1 / matches route False",
            lines,
        )

    def test_preset_export_markdown_renders_per_route_repository_count_consistency(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repository_count": 2,
                            "repositories": ["owner/repo", "owner/second", "owner/repo"],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Repository count consistency\uff1arepository 2 / route 2 / matches route True",
            lines,
        )

    def test_preset_export_markdown_flags_per_route_repository_count_mismatch(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repository_count": 1,
                            "repositories": ["owner/repo", "owner/second"],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Repository count consistency\uff1arepository 2 / route 1 / matches route False",
            lines,
        )

    def test_preset_export_markdown_filters_malformed_route_repository_list_entries(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repository_count": 2,
                            "repositories": [
                                "owner/repo",
                                {"bad": "repo"},
                                ["owner/nested"],
                                None,
                                "owner/second",
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("  - Repositories\uff1aowner/repo, owner/second", lines)
        self.assertIn(
            "  - Repository count consistency\uff1arepository 2 / route 2 / matches route True",
            lines,
        )
        self.assertIn("- Repository / unique evidence\uff1a2 / 0", lines)
        self.assertFalse(any("{'bad': 'repo'}" in line for line in lines))
        self.assertFalse(any("['owner/nested']" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_route_repository_payload_as_empty(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repository_count": 0,
                            "repositories": {"bad": "repo"},
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("  - Repositories\uff1a\u65e0", lines)
        self.assertIn(
            "  - Repository count consistency\uff1arepository 0 / route 0 / matches route True",
            lines,
        )
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertFalse(any("{'bad': 'repo'}" in line for line in lines))

    def test_preset_export_markdown_uses_route_count_fallbacks_when_counts_missing(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "path_count": 3,
                            "repositories": ["owner/repo", "owner/second", "owner/repo"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_repo"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Repository count consistency\uff1arepository 2 / route 2 / matches route True",
            lines,
        )
        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 3 / route 3 / matches route True; evidence 2 / route 2 / matches route True",
            lines,
        )

    def test_preset_export_markdown_flags_path_count_fallback_mismatch_when_example_count_missing(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "path_count": 2,
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_third"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 3 / route 2 / matches route False; evidence 3 / route 3 / matches route True",
            lines,
        )

    def test_preset_export_markdown_preserves_explicit_zero_route_level_counts(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repository_count": 0,
                            "example_count": 0,
                            "unique_evidence_count": 0,
                            "path_count": 5,
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Repository count consistency\uff1arepository 2 / route 0 / matches route False",
            lines,
        )
        self.assertIn("  - Paths / high / avg\uff1a5 / 0 / unknown", lines)
        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 2 / route 0 / matches route False; evidence 2 / route 0 / matches route False",
            lines,
        )

    def test_preset_export_markdown_uses_derived_fallbacks_for_malformed_route_counts(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "route_id": "validation::tests",
                            "repository_count": {"bad": "repo"},
                            "example_count": ["example"],
                            "unique_evidence_count": {"bad": "evidence"},
                            "path_count": ["path"],
                            "high_confidence_paths": {"bad": "high"},
                            "average_confidence": ["avg"],
                            "repositories": ["owner/repo", "owner/second", "owner/repo"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                                {"evidence_stable_id": "ev_repo"},
                            ],
                        }
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn(
            "  - Repository count consistency\uff1arepository 2 / route 2 / matches route True",
            lines,
        )
        self.assertIn("  - Paths / high / avg\uff1a0 / 0 / unknown", lines)
        self.assertIn(
            "  - Evidence/example count consistency\uff1aexample 3 / route 3 / matches route True; evidence 2 / route 2 / matches route True",
            lines,
        )
        self.assertFalse(any("{'bad': 'repo'}" in line for line in lines))
        self.assertFalse(any("['example']" in line for line in lines))
        self.assertFalse(any("{'bad': 'evidence'}" in line for line in lines))
        self.assertFalse(any("['path']" in line for line in lines))
        self.assertFalse(any("{'bad': 'high'}" in line for line in lines))
        self.assertFalse(any("['avg']" in line for line in lines))

    def test_preset_export_markdown_uses_export_summary_count_fallbacks_when_counts_missing(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {},
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a2 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 2", lines)
        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 2 / matches summary True",
            lines,
        )

    def test_preset_export_markdown_uses_derived_fallbacks_for_malformed_route_detail_summary_payload(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": ["bad summary"],
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a2 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 2", lines)
        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 2 / matches summary True",
            lines,
        )
        self.assertFalse(any("bad summary" in line for line in lines))

    def test_preset_export_markdown_uses_partial_export_summary_count_fallbacks(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "route_count": 1,
                        "unique_evidence_count": 3,
                    },
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a1 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 3", lines)
        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 1 / matches summary False; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 3 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_renders_malformed_export_preset_identity_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": {
                    "label": {"bad": "label"},
                    "preset_id": ["batch_repo"],
                    "selectors": {
                        "profile_path_move": {"bad": "move"},
                        "profile_path_route": ["route"],
                        "profile_path_repo": {"bad": "repo"},
                    },
                },
                "route_detail": {
                    "summary": {
                        "route_count": 0,
                        "example_count": 0,
                        "repository_count": 0,
                        "unique_evidence_count": 0,
                    },
                    "routes": [],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("## 1. Route detail preset", lines)
        self.assertIn("- Preset ID\uff1a``", lines)
        self.assertIn("- Move / route / repo\uff1a`` / `` / ``", lines)
        self.assertFalse(any("{'bad': 'label'}" in line for line in lines))
        self.assertFalse(any("['batch_repo']" in line for line in lines))
        self.assertFalse(any("{'bad': 'move'}" in line for line in lines))
        self.assertFalse(any("['route']" in line for line in lines))
        self.assertFalse(any("{'bad': 'repo'}" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_export_preset_payload_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": ["bad preset"],
                "route_detail": {
                    "summary": {
                        "route_count": 0,
                        "example_count": 0,
                        "repository_count": 0,
                        "unique_evidence_count": 0,
                    },
                    "routes": [],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("## 1. Route detail preset", lines)
        self.assertIn("- Preset ID\uff1a``", lines)
        self.assertIn("- Move / route / repo\uff1a`` / `` / ``", lines)
        self.assertFalse(any("bad preset" in line for line in lines))

    def test_preset_export_markdown_renders_malformed_export_selector_payload_as_fallbacks(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": {
                    "label": "Preset batch_repo",
                    "preset_id": "batch_repo",
                    "selectors": ["bad selectors"],
                },
                "route_detail": {
                    "summary": {
                        "route_count": 0,
                        "example_count": 0,
                        "repository_count": 0,
                        "unique_evidence_count": 0,
                    },
                    "routes": [],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("## 1. Preset batch_repo", lines)
        self.assertIn("- Preset ID\uff1a`batch_repo`", lines)
        self.assertIn("- Move / route / repo\uff1a`` / `` / ``", lines)
        self.assertFalse(any("bad selectors" in line for line in lines))

    def test_preset_export_markdown_preserves_explicit_zero_export_summary_counts(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "route_count": 0,
                        "example_count": 0,
                        "repository_count": 0,
                        "unique_evidence_count": 0,
                    },
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 0 / matches summary False; example 3 / summary 0 / matches summary False",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 0 / matches summary False; evidence 2 / summary 0 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_uses_derived_fallbacks_for_malformed_export_summary_counts(self):
        payload = preset_exports_payload({})
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "summary": {
                        "route_count": {"bad": "route"},
                        "example_count": ["example"],
                        "repository_count": {"bad": "repo"},
                        "unique_evidence_count": ["evidence"],
                    },
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Route / example\uff1a2 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 2", lines)
        self.assertIn(
            "- Route/example count consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 2 / matches summary True",
            lines,
        )
        self.assertFalse(any("{'bad': 'route'}" in line for line in lines))
        self.assertFalse(any("['example']" in line for line in lines))
        self.assertFalse(any("{'bad': 'repo'}" in line for line in lines))
        self.assertFalse(any("['evidence']" in line for line in lines))

    def test_preset_export_markdown_uses_top_level_summary_count_fallbacks_when_counts_missing(self):
        payload = preset_exports_payload({})
        payload["summary"] = {}
        payload["preset_validation"]["selected_preset_count"] = 1
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a1 / 2 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 2", lines)
        self.assertIn("- Selected preset count consistency\uff1a1 / summary 1 / matches summary True", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 2 / matches summary True",
            lines,
        )

    def test_preset_export_markdown_uses_partial_top_level_summary_count_fallbacks(self):
        payload = preset_exports_payload({})
        payload["summary"] = {
            "preset_count": 2,
            "route_count": 1,
            "unique_evidence_count": 3,
        }
        payload["preset_validation"]["selected_preset_count"] = 1
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a2 / 1 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 3", lines)
        self.assertIn("- Selected preset count consistency\uff1a1 / summary 2 / matches summary False", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 2 / summary 1 / matches summary False; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 2 / matches summary True; evidence 2 / summary 3 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_uses_derived_fallbacks_for_malformed_top_level_summary_counts(self):
        payload = preset_exports_payload({})
        payload["summary"] = {
            "preset_count": {"bad": "preset"},
            "route_count": ["route"],
            "example_count": {"bad": "example"},
            "repository_count": ["repo"],
            "unique_evidence_count": {"bad": "evidence"},
        }
        payload["preset_validation"]["selected_preset_count"] = 1
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a1 / 2 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 2", lines)
        self.assertIn("- Selected preset count consistency\uff1a1 / summary 1 / matches summary True", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 2 / summary 2 / matches summary True; example 3 / summary 3 / matches summary True",
            lines,
        )
        self.assertFalse(any("{'bad': 'preset'}" in line for line in lines))
        self.assertFalse(any("['route']" in line for line in lines))
        self.assertFalse(any("{'bad': 'example'}" in line for line in lines))
        self.assertFalse(any("['repo']" in line for line in lines))
        self.assertFalse(any("{'bad': 'evidence'}" in line for line in lines))

    def test_preset_export_markdown_uses_derived_fallbacks_for_malformed_top_level_summary_payload(self):
        payload = preset_exports_payload({})
        payload["summary"] = ["bad summary"]
        payload["preset_validation"]["selected_preset_count"] = 1
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a1 / 2 / 3", lines)
        self.assertIn("- Repository / unique evidence\uff1a2 / 2", lines)
        self.assertFalse(any("bad summary" in line for line in lines))

    def test_preset_export_markdown_preserves_explicit_zero_top_level_summary_counts(self):
        payload = preset_exports_payload({})
        payload["summary"] = {
            "preset_count": 0,
            "route_count": 0,
            "example_count": 0,
            "repository_count": 0,
            "unique_evidence_count": 0,
        }
        payload["preset_validation"]["selected_preset_count"] = 1
        payload["preset_validation"]["expected_route_count"] = 2
        payload["preset_validation"]["expected_example_count"] = 3
        payload["exports"] = [
            {
                "preset": preset("batch_repo"),
                "route_detail": {
                    "routes": [
                        {
                            "repositories": ["owner/repo", "owner/second"],
                            "examples": [
                                {"evidence_stable_id": "ev_repo"},
                                {"evidence_id": "ev_second"},
                            ],
                        },
                        {
                            "repositories": ["owner/repo"],
                            "examples": [{"evidence_stable_id": "ev_repo"}],
                        },
                    ],
                },
            }
        ]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Preset / route / example\uff1a0 / 0 / 0", lines)
        self.assertIn("- Repository / unique evidence\uff1a0 / 0", lines)
        self.assertIn("- Selected preset count consistency\uff1a1 / summary 0 / matches summary False", lines)
        self.assertIn(
            "- Expected route/example consistency\uff1aroute 2 / summary 0 / matches summary False; example 3 / summary 0 / matches summary False",
            lines,
        )
        self.assertIn(
            "- Repository/evidence count consistency\uff1arepository 2 / summary 0 / matches summary False; evidence 2 / summary 0 / matches summary False",
            lines,
        )

    def test_preset_export_markdown_uses_source_fixture_status_fallback_when_filters_empty(self):
        markdown = radar.render_archive_route_detail_preset_exports(
            preset_exports_payload({"source_fixture_status_filter": "ready"})
        )
        lines = markdown.splitlines()

        self.assertIn("- Source fixture status filter\uff1aready", lines)
        self.assertIn("- Source selector fixture filter\uff1aready", lines)
        self.assertIn("- Source selector filters\uff1a\u65e0", lines)

    def test_preset_export_markdown_renders_malformed_source_fixture_status_filter_as_empty(self):
        for source_fixture_status_filter in ({"bad": "status"}, ["ready"], 7):
            with self.subTest(source_fixture_status_filter=source_fixture_status_filter):
                payload = preset_exports_payload({})
                payload["source_fixture_status_filter"] = source_fixture_status_filter
                markdown = radar.render_archive_route_detail_preset_exports(payload)
                lines = markdown.splitlines()

                self.assertIn("- Source fixture status filter\uff1a\u65e0", lines)
                self.assertIn("- Source selector fixture filter\uff1a\u65e0", lines)
                self.assertFalse(any("{'bad': 'status'}" in line for line in lines))
                self.assertFalse(any("['ready']" in line for line in lines))

    def test_preset_export_markdown_prefers_source_selector_filter_over_status_filter(self):
        payload = preset_exports_payload(
            {
                "source_fixture_status_filter": "blocked",
                "source_selector_filters": {"fixture_validation_status": "ready"},
            }
        )
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture status filter\uff1ablocked", lines)
        self.assertIn("- Source selector fixture filter\uff1aready", lines)

    def test_preset_export_markdown_prefers_validation_fixture_selector_over_fixture_selector(self):
        payload = preset_exports_payload(
            {
                "source_fixture_status_filter": "blocked",
                "source_selector_filters": {
                    "fixture_validation_status": "ready",
                    "validation_fixture_status": "duplicate_ids",
                },
            }
        )
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture status filter\uff1ablocked", lines)
        self.assertIn("- Source selector fixture filter\uff1aduplicate_ids", lines)
        self.assertIn(
            "- Source selector filters\uff1afixture_validation_status=ready, validation_fixture_status=duplicate_ids",
            lines,
        )

    def test_preset_export_markdown_preserves_source_fixture_validation_status_and_match_flag(self):
        markdown = radar.render_archive_route_detail_preset_exports(
            preset_exports_payload(
                {
                    "validation_status": "ready",
                    "validation_matches_expected": False,
                }
            )
        )
        lines = markdown.splitlines()

        self.assertIn("- Source fixture validation\uff1aready / matches expected False", lines)

    def test_preset_export_markdown_falls_back_to_validation_status_for_source_fixture_validation(self):
        payload = preset_exports_payload(
            {
                "validation_status": "ready",
                "expected_validation_status": "ready",
            }
        )
        payload.pop("source_fixture_validation_status")
        payload.pop("source_fixture_validation_matches_expected")
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture validation\uff1aready / matches expected True", lines)

    def test_preset_export_markdown_falls_back_to_validation_status_for_source_fixture_mismatch(self):
        payload = preset_exports_payload(
            {
                "validation_status": "blocked",
                "expected_validation_status": "ready",
            }
        )
        payload.pop("source_fixture_validation_status")
        payload.pop("source_fixture_validation_matches_expected")
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture validation\uff1ablocked / matches expected False", lines)

    def test_preset_export_markdown_keeps_source_fixture_match_unknown_without_expected_status(self):
        payload = preset_exports_payload({"validation_status": "ready"})
        payload.pop("source_fixture_validation_status")
        payload.pop("source_fixture_validation_matches_expected")
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Expected validation status\uff1a\u65e0", lines)
        self.assertIn("- Source fixture validation\uff1aready / matches expected unknown", lines)

    def test_preset_export_markdown_preserves_explicit_source_fixture_match_flag_over_derived_match(self):
        payload = preset_exports_payload(
            {
                "validation_status": "ready",
                "validation_matches_expected": False,
                "expected_validation_status": "ready",
            }
        )
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture validation\uff1aready / matches expected False", lines)

    def test_preset_export_markdown_renders_malformed_source_fixture_validation_as_unknown(self):
        payload = preset_exports_payload({})
        payload["source_fixture_validation_status"] = {"bad": "status"}
        payload["source_fixture_validation_matches_expected"] = ["bad"]
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture validation\uff1aunknown / matches expected unknown", lines)
        self.assertFalse(any("{'bad': 'status'}" in line for line in lines))
        self.assertFalse(any("['bad']" in line for line in lines))

    def test_preset_export_markdown_renders_missing_fixture_counts_as_unknown(self):
        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload({}))
        lines = markdown.splitlines()

        self.assertIn("- Source fixture count\uff1aunknown / unfiltered unknown", lines)
        self.assertIn("- Source fixture matching expected\uff1aunknown / unfiltered unknown", lines)

    def test_preset_export_markdown_preserves_numeric_fixture_counts(self):
        markdown = radar.render_archive_route_detail_preset_exports(
            preset_exports_payload(
                {
                    "source_fixture_count": 0,
                    "source_unfiltered_fixture_count": 4,
                    "source_fixture_matching_expected_count": 0,
                    "source_fixture_unfiltered_matching_expected_count": 4,
                }
            )
        )
        lines = markdown.splitlines()

        self.assertIn("- Source fixture count\uff1a0 / unfiltered 4", lines)
        self.assertIn("- Source fixture matching expected\uff1a0 / unfiltered 4", lines)

    def test_preset_export_markdown_renders_malformed_fixture_counts_as_unknown(self):
        payload = preset_exports_payload(
            {
                "source_fixture_count": {"bad": "count"},
                "source_unfiltered_fixture_count": ["bad"],
                "source_fixture_matching_expected_count": "2",
                "source_fixture_unfiltered_matching_expected_count": True,
            }
        )
        markdown = radar.render_archive_route_detail_preset_exports(payload)
        lines = markdown.splitlines()

        self.assertIn("- Source fixture count\uff1aunknown / unfiltered unknown", lines)
        self.assertIn("- Source fixture matching expected\uff1aunknown / unfiltered unknown", lines)
        self.assertFalse(any("{'bad': 'count'}" in line for line in lines))
        self.assertFalse(any("['bad']" in line for line in lines))

    def test_preset_export_markdown_renders_empty_fixture_status_counts(self):
        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload({}))
        lines = markdown.splitlines()

        self.assertIn("- Source fixture status counts\uff1a\u65e0", lines)
        self.assertIn("- Source all fixture status counts\uff1a\u65e0", lines)

    def test_preset_export_markdown_orders_fixture_status_counts(self):
        markdown = radar.render_archive_route_detail_preset_exports(
            preset_exports_payload(
                {
                    "source_fixture_status_counts": {"ready": 2, "blocked": 1, "duplicate_ids": 1},
                    "source_all_fixture_status_counts": {"ready": 3, "blocked": 2, "duplicate_ids": 1},
                }
            )
        )
        lines = markdown.splitlines()

        self.assertIn("- Source fixture status counts\uff1ablocked=1, duplicate_ids=1, ready=2", lines)
        self.assertIn("- Source all fixture status counts\uff1ablocked=2, duplicate_ids=1, ready=3", lines)

    def test_preset_export_markdown_renders_malformed_fixture_status_count_payloads_as_empty(self):
        for source_fixture_status_counts in ("ready=2", ["ready"], 7):
            with self.subTest(source_fixture_status_counts=source_fixture_status_counts):
                markdown = radar.render_archive_route_detail_preset_exports(
                    preset_exports_payload(
                        {
                            "source_fixture_status_counts": source_fixture_status_counts,
                            "source_all_fixture_status_counts": source_fixture_status_counts,
                        }
                    )
                )
                lines = markdown.splitlines()

                self.assertIn("- Source fixture status counts\uff1a\u65e0", lines)
                self.assertIn("- Source all fixture status counts\uff1a\u65e0", lines)

    def test_preset_export_markdown_filters_malformed_fixture_status_count_entries(self):
        markdown = radar.render_archive_route_detail_preset_exports(
            preset_exports_payload(
                {
                    "source_fixture_status_counts": {
                        "ready": 2,
                        "blocked": 1,
                        "bad_dict": {"bad": "count"},
                        "bad_list": ["bad"],
                        "bad_none": None,
                        7: "bad_key",
                    },
                    "source_all_fixture_status_counts": {
                        "ready": 3,
                        "duplicate_ids": 1,
                        "bad_dict": {"bad": "count"},
                        "bad_list": ["bad"],
                        "bad_none": None,
                        7: "bad_key",
                    },
                }
            )
        )
        lines = markdown.splitlines()

        self.assertIn("- Source fixture status counts\uff1ablocked=1, ready=2", lines)
        self.assertIn("- Source all fixture status counts\uff1aduplicate_ids=1, ready=3", lines)
        self.assertFalse(any("{'bad': 'count'}" in line for line in lines))
        self.assertFalse(any("['bad']" in line for line in lines))
        self.assertFalse(any("7=bad_key" in line for line in lines))

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

    def test_fixture_driven_preset_batch_exports_preserve_provenance_and_summaries(self):
        source_payload = fixture_batch_selector_payload()
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(None, preset_export_args())

        self.assertEqual(payload["source_fixture_id"], "ready_batch")
        self.assertEqual(payload["source_fixture_status_filter"], "ready")
        self.assertEqual(payload["source_fixture_count"], 2)
        self.assertEqual(payload["source_unfiltered_fixture_count"], 4)
        self.assertEqual(payload["source_fixture_matching_expected_count"], 2)
        self.assertEqual(payload["source_fixture_unfiltered_matching_expected_count"], 4)
        self.assertEqual(payload["source_fixture_status_counts"], {"ready": 2})
        self.assertEqual(payload["source_all_fixture_status_counts"], {"blocked": 1, "duplicate_ids": 1, "ready": 2})
        self.assertEqual(payload["source_fixture_validation_status"], "ready")
        self.assertIs(payload["source_fixture_validation_matches_expected"], True)
        self.assertEqual(payload["expected_validation_status"], "ready")
        self.assertEqual(payload["preset_validation"]["status"], "ready")
        self.assertEqual(payload["preset_validation"]["ready_preset_count"], 2)
        self.assertEqual(payload["summary"]["preset_count"], 2)
        self.assertEqual(payload["summary"]["route_count"], 2)
        self.assertEqual(payload["summary"]["example_count"], 3)
        self.assertEqual(payload["summary"]["repository_count"], 2)
        self.assertEqual(payload["summary"]["unique_evidence_count"], 2)
        self.assertEqual([item["repo"] for item in detail_calls], ["owner/repo", "owner/second"])
        self.assertEqual([export["preset"]["preset_id"] for export in payload["exports"]], ["batch_repo", "batch_second"])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("Source fixture", markdown)
        self.assertIn("ready_batch", markdown)
        self.assertIn("Source fixture count", markdown)
        self.assertIn("2 / unfiltered 4", markdown)
        self.assertIn("Source fixture matching expected", markdown)
        self.assertIn("Source fixture status counts", markdown)
        self.assertIn("ready=2", markdown)
        self.assertIn("Source all fixture status counts", markdown)
        self.assertIn("blocked=1, duplicate_ids=1, ready=2", markdown)
        self.assertIn("Preset / route / example", markdown)
        self.assertIn("2 / 2 / 3", markdown)

    def test_fixture_driven_preset_batch_honors_preset_id_scope(self):
        source_payload = fixture_batch_selector_payload()
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(
                None,
                preset_export_args(preset_ids=["batch_second"]),
            )

        self.assertEqual(payload["source_fixture_id"], "ready_batch")
        self.assertEqual(payload["requested_preset_ids"], ["batch_second"])
        self.assertEqual(payload["source_fixture_status_filter"], "ready")
        self.assertEqual(payload["source_fixture_count"], 2)
        self.assertEqual(payload["source_unfiltered_fixture_count"], 4)
        self.assertEqual(payload["preset_validation"]["status"], "ready")
        self.assertEqual(payload["preset_validation"]["selected_preset_count"], 1)
        self.assertEqual(payload["preset_validation"]["ready_preset_count"], 1)
        self.assertEqual(payload["preset_validation"]["expected_route_count"], 1)
        self.assertEqual(payload["preset_validation"]["expected_example_count"], 1)
        self.assertEqual(payload["summary"]["preset_count"], 1)
        self.assertEqual(payload["summary"]["route_count"], 1)
        self.assertEqual(payload["summary"]["example_count"], 1)
        self.assertEqual(payload["summary"]["repository_count"], 1)
        self.assertEqual(payload["summary"]["unique_evidence_count"], 1)
        self.assertEqual(detail_calls, [
            {
                "move": "boundary_design::Architecture boundary",
                "route": "validation::tests",
                "repo": "owner/second",
            }
        ])
        self.assertEqual([export["preset"]["preset_id"] for export in payload["exports"]], ["batch_second"])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("ready_batch", markdown)
        self.assertIn("Source fixture count", markdown)
        self.assertIn("2 / unfiltered 4", markdown)
        self.assertIn("Selected / ready / unmatched", markdown)
        self.assertIn("1 / 1 / 0", markdown)
        self.assertIn("Preset / route / example", markdown)
        self.assertIn("1 / 1 / 1", markdown)

    def test_fixture_driven_preset_batch_markdown_honors_multiple_preset_ids(self):
        source_payload = fixture_batch_selector_payload(extra_unselected_preset=True)
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(
                None,
                preset_export_args(preset_ids=["batch_repo", "batch_second"]),
            )

        self.assertEqual(payload["requested_preset_ids"], ["batch_repo", "batch_second"])
        self.assertEqual(payload["source_fixture_id"], "ready_batch")
        self.assertEqual(payload["source_fixture_count"], 2)
        self.assertEqual(payload["source_unfiltered_fixture_count"], 4)
        self.assertEqual(payload["preset_validation"]["status"], "ready")
        self.assertEqual(payload["preset_validation"]["selected_preset_count"], 2)
        self.assertEqual(payload["preset_validation"]["ready_preset_count"], 2)
        self.assertEqual(payload["preset_validation"]["source_bundle_preset_count"], 3)
        self.assertEqual(payload["summary"]["preset_count"], 2)
        self.assertEqual(payload["summary"]["route_count"], 2)
        self.assertEqual(payload["summary"]["example_count"], 3)
        self.assertEqual([item["repo"] for item in detail_calls], ["owner/repo", "owner/second"])
        self.assertEqual([export["preset"]["preset_id"] for export in payload["exports"]], ["batch_repo", "batch_second"])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("Source fixture", markdown)
        self.assertIn("ready_batch", markdown)
        self.assertIn("Source presets", markdown)
        self.assertIn("Selected / ready / unmatched", markdown)
        self.assertIn("2 / 2 / 0", markdown)
        self.assertIn("Preset / route / example", markdown)
        self.assertIn("2 / 2 / 3", markdown)
        self.assertIn("Preset batch_repo", markdown)
        self.assertIn("Preset batch_second", markdown)
        self.assertIn("batch_repo", markdown)
        self.assertIn("batch_second", markdown)
        self.assertNotIn("batch_unselected", markdown)

    def test_fixture_source_filters_are_carried_into_preset_args(self):
        source_filters = {
            "validation_fixture_status": "ready",
            "confidence_source": "auto",
            "signal_group": "evidence",
            "track": "agent",
            "min_score": 72,
            "path_move": "all",
            "path_route": "all",
            "path_repo": "all",
        }
        source_payload = fixture_batch_selector_payload(source_filters=source_filters)
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                    "confidence_source": args.profile_path_confidence_source,
                    "signal_group": args.archive_signal_group,
                    "track": args.archive_track,
                    "min_track_score": args.min_track_score,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(
                None,
                preset_export_args(preset_ids=["batch_repo"]),
            )

        self.assertEqual(payload["source_selector_filters"], source_filters)
        self.assertEqual(payload["source_fixture_id"], "ready_batch")
        self.assertEqual(payload["summary"]["preset_count"], 1)
        self.assertEqual(detail_calls, [
            {
                "move": "boundary_design::Architecture boundary",
                "route": "validation::tests",
                "repo": "owner/repo",
                "confidence_source": "auto",
                "signal_group": "evidence",
                "track": "agent",
                "min_track_score": 72,
            }
        ])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("Source selector filters", markdown)
        self.assertIn("confidence_source=auto", markdown)
        self.assertIn("signal_group=evidence", markdown)
        self.assertIn("track=agent", markdown)
        self.assertIn("min_score=72", markdown)
        self.assertIn("path_move=all", markdown)
        self.assertIn("path_route=all", markdown)
        self.assertIn("path_repo=all", markdown)

    def test_preset_selectors_override_conflicting_source_path_filters(self):
        source_filters = {
            "validation_fixture_status": "ready",
            "confidence_source": "auto",
            "signal_group": "pattern",
            "track": "developer_tools",
            "min_score": 64,
            "path_move": "source_move::Should not win",
            "path_route": "source_route::should_not_win",
            "path_repo": "source/repo",
        }
        source_payload = fixture_batch_selector_payload(source_filters=source_filters)
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                    "confidence_source": args.profile_path_confidence_source,
                    "signal_group": args.archive_signal_group,
                    "track": args.archive_track,
                    "min_track_score": args.min_track_score,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(
                None,
                preset_export_args(preset_ids=["batch_second"]),
            )

        self.assertEqual(payload["source_selector_filters"], source_filters)
        self.assertEqual(payload["summary"]["preset_count"], 1)
        self.assertEqual(detail_calls, [
            {
                "move": "boundary_design::Architecture boundary",
                "route": "validation::tests",
                "repo": "owner/second",
                "confidence_source": "auto",
                "signal_group": "pattern",
                "track": "developer_tools",
                "min_track_score": 64,
            }
        ])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("Source selector filters", markdown)
        self.assertIn("validation_fixture_status=ready", markdown)
        self.assertIn("confidence_source=auto", markdown)
        self.assertIn("signal_group=pattern", markdown)
        self.assertIn("track=developer_tools", markdown)
        self.assertIn("min_score=64", markdown)
        self.assertIn("path_move=source_move::Should not win", markdown)
        self.assertIn("path_route=source_route::should_not_win", markdown)
        self.assertIn("path_repo=source/repo", markdown)

    def test_dashboard_single_fixture_source_filters_are_carried_into_preset_args(self):
        source_filters = {
            "fixture_validation_status": "ready",
            "confidence_source": "auto",
            "signal_group": "drift",
            "track": "local-first",
            "min_score": 81,
            "path_move": "all",
            "path_route": "all",
            "path_repo": "all",
        }
        source_payload = dashboard_ready_fixture_bundle(source_filters=source_filters)
        selector_payload = fixture_batch_selector_payload(source_filters={"validation_fixture_status": "ready"})
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                    "confidence_source": args.profile_path_confidence_source,
                    "signal_group": args.archive_signal_group,
                    "track": args.archive_track,
                    "min_track_score": args.min_track_score,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=selector_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(
                None,
                preset_export_args(fixture_id=None, preset_ids=["dashboard_ready"]),
            )

        self.assertEqual(payload["source_fixture_id"], "ready_dashboard")
        self.assertEqual(payload["source_selector_filters"], source_filters)
        self.assertEqual(payload["source_fixture_status_filter"], "ready")
        self.assertEqual(payload["source_fixture_validation_status"], "ready")
        self.assertEqual(payload["preset_validation"]["status"], "ready")
        self.assertEqual(payload["summary"]["preset_count"], 1)
        self.assertEqual(detail_calls, [
            {
                "move": "boundary_design::Architecture boundary",
                "route": "validation::tests",
                "repo": "owner/repo",
                "confidence_source": "auto",
                "signal_group": "drift",
                "track": "local-first",
                "min_track_score": 81,
            }
        ])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("Source selector filters", markdown)
        self.assertIn("fixture_validation_status=ready", markdown)
        self.assertIn("confidence_source=auto", markdown)
        self.assertIn("signal_group=drift", markdown)
        self.assertIn("track=local-first", markdown)
        self.assertIn("min_score=81", markdown)
        self.assertIn("path_move=all", markdown)
        self.assertIn("path_route=all", markdown)
        self.assertIn("path_repo=all", markdown)

    def test_dashboard_single_fixture_preset_selectors_override_conflicting_source_path_filters(self):
        source_filters = {
            "fixture_validation_status": "ready",
            "confidence_source": "auto",
            "signal_group": "time_series",
            "track": "protocol",
            "min_score": 69,
            "path_move": "dashboard_move::Should not win",
            "path_route": "dashboard_route::should_not_win",
            "path_repo": "dashboard/repo",
        }
        source_payload = dashboard_ready_fixture_bundle(source_filters=source_filters)
        selector_payload = fixture_batch_selector_payload(source_filters={"validation_fixture_status": "ready"})
        detail_calls = []

        def archive_detail_stub(conn, args):
            detail_calls.append(
                {
                    "move": args.profile_path_move,
                    "route": args.profile_path_route,
                    "repo": args.profile_path_repo,
                    "confidence_source": args.profile_path_confidence_source,
                    "signal_group": args.archive_signal_group,
                    "track": args.archive_track,
                    "min_track_score": args.min_track_score,
                }
            )
            return fake_route_detail_payload(args)

        with mock.patch.object(radar, "read_json_payload", return_value=source_payload), \
            mock.patch.object(radar, "archive_route_selectors_payload", return_value=selector_payload), \
            mock.patch.object(radar, "archive_route_detail_payload", side_effect=archive_detail_stub):
            payload = radar.archive_route_detail_preset_exports_payload(
                None,
                preset_export_args(fixture_id=None, preset_ids=["dashboard_ready"]),
            )

        self.assertEqual(payload["source_selector_filters"], source_filters)
        self.assertEqual(payload["summary"]["preset_count"], 1)
        self.assertEqual(detail_calls, [
            {
                "move": "boundary_design::Architecture boundary",
                "route": "validation::tests",
                "repo": "owner/repo",
                "confidence_source": "auto",
                "signal_group": "time_series",
                "track": "protocol",
                "min_track_score": 69,
            }
        ])

        markdown = radar.render_archive_route_detail_preset_exports(payload)
        self.assertIn("Source selector filters", markdown)
        self.assertIn("fixture_validation_status=ready", markdown)
        self.assertIn("confidence_source=auto", markdown)
        self.assertIn("signal_group=time_series", markdown)
        self.assertIn("track=protocol", markdown)
        self.assertIn("min_score=69", markdown)
        self.assertIn("path_move=dashboard_move::Should not win", markdown)
        self.assertIn("path_route=dashboard_route::should_not_win", markdown)
        self.assertIn("path_repo=dashboard/repo", markdown)


if __name__ == "__main__":
    unittest.main()
