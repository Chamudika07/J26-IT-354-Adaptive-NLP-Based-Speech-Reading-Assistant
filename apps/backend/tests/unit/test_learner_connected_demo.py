"""Connected synthetic file round trip; no database, network or live endpoints."""

import ast
import json
from datetime import UTC, datetime
from decimal import Decimal
from importlib.util import resolve_name
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.learner_modelling.connected_demo import (
    DemoContext,
    build_connected_preview,
    build_connected_replay,
    main,
)
from app.modules.learner_modelling.longitudinal import LongitudinalWindow
from app.modules.learner_modelling.router import router

BASE = Path(__file__).resolve().parents[3] / "mobile/src/features/learnerModelling/preview"
CONTEXT = DemoContext(task="independent_reading", tier="intermediate", mode="adaptive")
WINDOW = LongitudinalWindow(
    start_at_utc=datetime(2026, 1, 1, tzinfo=UTC), end_at_utc=datetime(2026, 1, 31, tzinfo=UTC)
)


def sample():
    return json.loads((BASE / "connectedSessionExample.json").read_text(encoding="utf-8"))


def build(data):
    return build_connected_preview(json.dumps(data), WINDOW, CONTEXT)


def test_success_reuses_real_engine_and_minimized_projection_without_io():
    with patch("socket.socket", side_effect=AssertionError("No network")):
        result = build(sample())
    assert result.includedSessionCount == 6
    assert result.metrics[0].latest_value == Decimal("0.96")
    assert result.recommendation is not None
    assert result.recommendation.action == "Try a harder reading level"
    assert result.recommendation.proposed == ("Reading level: advanced",)
    assert result.recommendation.changes_applied is False
    assert result.recommendation.automatic_application_allowed is False
    assert result.recommendation.evidence_state == "sufficient"
    for field in ("learner_id", "session_id", "actor_id", "row_version", '"records"'):
        assert field not in result.model_dump_json()
    assert all(
        route.endpoint.__module__ != build_connected_preview.__module__ for route in router.routes
    )


def test_artifact_and_pin_match_backend_recalculation_for_exact_example():
    pinned = json.loads((BASE / "connectedSessionContract.json").read_text(encoding="utf-8"))
    artifact = json.loads((BASE / "connectedSessionPreview.json").read_text(encoding="utf-8"))
    assert artifact == pinned
    result = build_connected_preview(
        (BASE / "connectedSessionInput.json").read_text(encoding="utf-8"),
        LongitudinalWindow.model_validate(
            {
                "start_at_utc": artifact["reportingStartUtc"],
                "end_at_utc": artifact["reportingEndUtc"],
            }
        ),
        DemoContext.model_validate(artifact["context"]),
        generated_at=datetime.fromisoformat(artifact["generatedAt"]),
    )
    assert result.model_dump(mode="json") == artifact


@pytest.mark.parametrize("count", [0, 1, 2])
def test_empty_or_insufficient_evidence_never_proposes_advice(count):
    data = sample()
    data["records"] = data["records"][:count]
    result = build(data)
    assert result.includedSessionCount == count
    assert result.recommendation is None
    assert "unavailable" in result.recommendationExplanation[0]
    if count:
        assert all(metric.evidence_state == "limited" for metric in result.metrics)


def test_missing_measurements_remain_missing_and_advice_unavailable():
    data = sample()
    for r in data["records"]:
        r.update(attempted=0, correct=0, activeMs=0, hesitations=None)
    result = build(data)
    assert result.recommendation is None
    assert all(metric.latest_value is None for metric in result.metrics)


def test_context_completion_and_period_selection_use_same_sessions():
    data = sample()
    for index, change in enumerate(
        [
            {"completion": "abandoned"},
            {"task": "guided_echo_reading"},
            {"tier": "early"},
            {"mode": "baseline_fixed"},
            {"start": "2025-12-31T00:00:00.000Z"},
        ]
    ):
        data["records"][index].update(change)
    result = build(data)
    assert result.includedSessionCount == 1 and result.excludedSessionCount == 5
    assert result.recommendation is None
    reordered = build({**data, "records": list(reversed(data["records"]))})
    assert result.metrics == reordered.metrics
    assert result.recommendationExplanation == reordered.recommendationExplanation


@pytest.mark.parametrize(
    "change",
    [
        {"correct": 101},
        {"activeMs": 999999},
        {"pauseMs": 999999},
        {"attempted": "100"},
        {"attempted": True},
        {"completion": "unknown"},
        {"task": "unknown"},
        {"start": "2026-01-01"},
        {"learner_id": "private"},
    ],
)
def test_invalid_inputs_fail_as_whole_batch(change):
    data = sample()
    data["records"][0].update(change)
    with pytest.raises(ValueError):
        build(data)


def test_duplicate_and_mislabeled_envelopes_rejected():
    data = sample()
    data["records"].append(data["records"][0])
    with pytest.raises(ValueError):
        build(data)
    for change in [
        {"synthetic": False},
        {"synthetic": 1},
        {"verifiedTelemetry": True},
        {"role": "guardian"},
        {"learner_id": "private"},
        {"version": 3},
    ]:
        with pytest.raises(ValueError):
            build(sample() | change)


def test_context_validation_and_development_cli_opt_in(monkeypatch):
    with pytest.raises(ValueError):
        DemoContext(task="unknown", tier="intermediate", mode="adaptive")
    monkeypatch.setattr("sys.argv", ["connected_demo"])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 2


def _import_targets(source: str, module: str) -> set[str]:
    """Resolve plain, parent-package and relative imports; not a text substring check."""
    targets = set()
    package = module.rpartition(".")[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = resolve_name("." * node.level + base, package)
            targets.add(base)
            targets.update(f"{base}.{alias.name}" for alias in node.names)
    return targets


def test_no_production_importer_or_database_network_dependencies():
    import app.modules.learner_modelling.connected_demo as module

    path = Path(module.__file__).resolve()
    app = path.parents[2]
    # Reviewed file-only entry points may share synthetic fixtures. They are NOT
    # production services: every other app module must remain unable to import them.
    offline = {
        "app.modules.learner_modelling.connected_demo",
        "app.modules.learner_modelling.role_scenarios",
        "app.modules.learner_modelling.educator_students",
    }
    forbidden = (
        "httpx",
        "requests",
        "socket",
        "sqlalchemy",
        "app.db",
        "app.modules.auth",
        "app.modules.learners",
    )
    for other in app.rglob("*.py"):
        name = ".".join(("app", *other.relative_to(app).with_suffix("").parts))
        imports = _import_targets(other.read_text(encoding="utf-8"), name)
        if name in offline:
            assert not any(t == f or t.startswith(f + ".") for t in imports for f in forbidden), (
                name
            )
        else:
            assert not any(t == f or t.startswith(f + ".") for t in imports for f in offline), name


@pytest.mark.parametrize(
    "statement",
    [
        "from app.modules.learner_modelling.connected_demo import SampleFile",
        "import app.modules.learner_modelling.connected_demo as demo",
        "from app.modules.learner_modelling import connected_demo",
        "from .connected_demo import SampleFile",
        "from . import connected_demo",
    ],
)
def test_isolation_guard_detects_production_import_forms(statement):
    assert "app.modules.learner_modelling.connected_demo" in _import_targets(
        statement, "app.modules.learner_modelling.service"
    )


@pytest.mark.parametrize("mode", ["baseline_fixed", "manual_override"])
def test_mode_precedence_and_no_automatic_changes(mode):
    data = sample()
    for r in data["records"]:
        r["mode"] = mode
    result = build_connected_preview(
        json.dumps(data),
        WINDOW,
        DemoContext(task="independent_reading", tier="intermediate", mode=mode),
    )
    assert result.recommendation is not None
    assert not result.recommendation.proposed
    assert result.recommendation.changes_applied is False
    assert result.recommendation.fixed_baseline == (mode == "baseline_fixed")
    assert result.recommendation.manual_control_prevents_adjustment == (mode == "manual_override")


def test_half_open_boundaries_and_invalid_excluded_records():
    data = sample()
    data["records"][0].update(start="2025-12-31T23:59:59.999Z")
    data["records"][1].update(start="2026-01-01T00:00:00.000Z")
    data["records"][2].update(start="2026-01-31T00:00:00.000Z", end="2026-01-31T00:01:00.000Z")
    assert build(data).includedSessionCount == 4
    data["records"][0]["correct"] = 101
    with pytest.raises(ValueError):
        build(data)


def test_connected_replay_prefixes_use_backend_metrics_history_and_report_evidence():
    from app.modules.learner_modelling.adaptation_mapping import CompletedSessionEvidence
    from app.modules.learner_modelling.connected_demo import SampleFile
    from app.modules.learner_modelling.dashboard_projections import project_learner_progress
    from app.modules.learner_modelling.longitudinal import LongitudinalObservation
    from app.modules.learner_modelling.report_evidence import build_structured_report

    raw = json.dumps(sample())
    steps = build_connected_replay(
        raw, WINDOW, CONTEXT, generated_at=datetime(2026, 10, 20, tzinfo=UTC)
    )
    records = SampleFile.model_validate_json(raw).records
    assert len(steps) == 7
    for count, step in enumerate(steps):
        assert step.includedSessionCount == len(step.history) == count
        evidence = CompletedSessionEvidence.from_observations(
            [
                LongitudinalObservation.from_telemetry(
                    r.ingest().to_session_telemetry(session_id=str(r.id))
                )
                for r in records[:count]
            ],
            WINDOW,
        )
        report = build_structured_report(project_learner_progress(evidence.report))
        assert step.reportStatements == tuple(
            item.text for item in report.narrative_request.approved_statements
        )
        from app.modules.learner_modelling.adaptation import AdaptationThresholds

        if count < AdaptationThresholds().min_sessions_for_recommendation:
            assert step.recommendation is None
        else:
            assert step.recommendation is not None
        if count:
            assert all(
                metric.evidence_state == ("sufficient" if count >= 6 else "limited")
                for metric in step.metrics
            )
            assert step.history[-1].accuracy == Decimal(".96")
            assert step.history[-1].wpm == Decimal("100")
            assert step.history[-1].hesitation == Decimal(".02")
    assert len({step.generatedAt for step in steps}) == 1


def test_bundled_replay_matches_validated_source_and_pin():
    actual = json.loads((BASE / "connectedSessionReplay.json").read_text(encoding="utf-8"))
    pin = json.loads((BASE / "connectedSessionReplayContract.json").read_text(encoding="utf-8"))
    artifact = json.loads((BASE / "connectedSessionPreview.json").read_text(encoding="utf-8"))
    steps = build_connected_replay(
        (BASE / "connectedSessionInput.json").read_text(encoding="utf-8"),
        LongitudinalWindow.model_validate(
            {
                "start_at_utc": artifact["reportingStartUtc"],
                "end_at_utc": artifact["reportingEndUtc"],
            }
        ),
        DemoContext.model_validate(artifact["context"]),
        generated_at=datetime.fromisoformat(artifact["generatedAt"]),
    )
    assert actual == pin == [step.model_dump(mode="json") for step in steps]


@pytest.mark.parametrize("invalid", ["measurements", "duplicates"])
def test_invalid_cli_input_cannot_overwrite_valid_artifacts(tmp_path, monkeypatch, invalid):
    data = sample()
    if invalid == "measurements":
        data["records"][0]["correct"] = 101
    else:
        data["records"].append(data["records"][0])
    input_path = tmp_path / "sample.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "connected_demo",
            "--development-synthetic-only",
            "--input",
            str(input_path),
            "--start",
            "2026-01-01T00:00:00Z",
            "--end",
            "2026-01-31T00:00:00Z",
            "--task",
            "independent_reading",
            "--tier",
            "intermediate",
            "--mode",
            "adaptive",
        ],
    )
    with patch("pathlib.Path.write_text") as write:
        with pytest.raises(SystemExit) as result:
            main()
        assert result.value.code == 2
        write.assert_not_called()


def test_custom_measurements_change_actual_backend_results():
    data = sample()
    original = build(data)
    data["records"][-1].update(correct=50, activeMs=30000, hesitations=10)
    changed = build(data)
    assert changed.includedSessionCount == original.includedSessionCount
    assert changed.history[-1].accuracy == Decimal("0.5")
    assert changed.history[-1].wpm == Decimal("200")
    assert changed.history[-1].hesitation == Decimal("0.1")
    assert changed.reportStatements != original.reportStatements
    assert changed.recommendation is None or changed.recommendation.changes_applied is False


def test_cli_derives_input_window_and_context_without_touching_repo(tmp_path, monkeypatch):
    source = tmp_path / "custom.json"
    source.write_text(json.dumps(sample()), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "connected_demo",
            "--development-synthetic-only",
            "--input",
            str(source),
            "--derive-window-context",
        ],
    )
    captured = {}

    def capture(path, text, **kwargs):
        captured[path.name] = text

    with (
        patch.object(Path, "write_text", capture),
        patch("socket.socket", side_effect=AssertionError()),
    ):
        main()
    result = json.loads(captured["connectedSessionPreview.json"])
    assert result["includedSessionCount"] == 6
    assert result["context"] == CONTEXT.model_dump(mode="json")
    assert result == json.loads(captured["connectedSessionContract.json"])
    assert len(json.loads(captured["connectedSessionReplay.json"])) == 7
    assert "localReportSnapshot.json" not in captured


@pytest.mark.parametrize("case", ["empty", "mixed", "duplicate", "conflict"])
def test_derived_import_rejects_ambiguous_inputs_before_writing(tmp_path, monkeypatch, case):
    data = sample()
    if case == "empty":
        data["records"] = []
    elif case == "mixed":
        data["records"][0]["tier"] = "early"
    elif case == "duplicate":
        data["records"].append(data["records"][0])
    source = tmp_path / "custom.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    args = [
        "connected_demo",
        "--development-synthetic-only",
        "--input",
        str(source),
        "--derive-window-context",
    ]
    if case == "conflict":
        args += ["--tier", "early"]
    monkeypatch.setattr("sys.argv", args)
    with patch.object(Path, "write_text") as write, pytest.raises(SystemExit):
        main()
    write.assert_not_called()
