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

    def test_preset_export_markdown_renders_empty_source_selector_filters(self):
        markdown = radar.render_archive_route_detail_preset_exports(preset_exports_payload({}))
        lines = markdown.splitlines()

        self.assertIn("- Source selector fixture filter\uff1a\u65e0", lines)
        self.assertIn("- Source selector filters\uff1a\u65e0", lines)

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
