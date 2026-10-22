"""Offline export tests: synthetic fixtures only, no daemon or database access."""

import ast
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.modules.learner_modelling import local_report_snapshot as export
from app.modules.learner_modelling.report_contracts import NarrativeDraft
from app.modules.learner_modelling.report_evidence import build_structured_report
from app.modules.learner_modelling.report_narrative import (
    NarrativeUnavailable,
    ReportGenerationResult,
)
from app.modules.learner_modelling.report_synthetic import build_synthetic_projection


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    forbidden = Mock(
        side_effect=AssertionError("No actual HTTP or database access in export tests")
    )
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


def valid_result() -> ReportGenerationResult:
    report = build_structured_report(build_synthetic_projection())
    request = report.narrative_request
    return ReportGenerationResult(
        report,
        "validated_narrative",
        NarrativeDraft(
            schema_version=request.schema_version,
            report_fingerprint=request.report_fingerprint,
            statements=request.approved_statements,
        ),
        None,
    )


def snapshot() -> export.LocalReportSnapshot:
    return export.build_display_snapshot(
        valid_result(), model="qwen3:4b", generated_at=datetime(2026, 1, 2, tzinfo=UTC)
    )


def test_export_is_minimal_validated_display_projection_and_matches_mobile_contract() -> None:
    data = snapshot().model_dump(mode="json")
    contract = json.loads(
        (export._MOBILE_DIRECTORY / "syntheticReportDisplayContract.json").read_text()
    )
    assert {key: data[key] for key in contract} == contract
    assert set(data) == {
        "schemaVersion",
        "synthetic",
        "source",
        "validated",
        "role",
        "model",
        "generatedAt",
        "reportingStartUtc",
        "reportingEndUtc",
        "statements",
    }
    assert data["synthetic"] is True and data["validated"] is True
    assert data["source"] == "local-ollama"
    assert data["generatedAt"] == "2026-01-02T00:00:00+00:00"
    assert len(data["statements"]) == 14
    serialized = json.dumps(data)
    for forbidden in (
        "session_id",
        "learner_id",
        "synthetic-openai",
        "evidence_ref",
        "report_fingerprint",
        "prompt",
        "API_KEY",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize("mutation", ["status", "missing", "fabrication", "role", "model", "time"])
def test_export_revalidates_and_rejects_invalid_or_cross_role_results(mutation: str) -> None:
    result = valid_result()
    assert result.narrative is not None
    if mutation == "status":
        result = replace(result, status="unavailable")
    elif mutation == "missing":
        result = replace(result, narrative=None)
    elif mutation == "role":
        result = replace(result, factual_report=replace(result.factual_report, role="guardian"))
    elif mutation == "fabrication":
        statement = result.narrative.statements[0].model_copy(update={"text": "Score 999"})
        result = replace(
            result,
            narrative=result.narrative.model_copy(
                update={"statements": (statement, *result.narrative.statements[1:])}
            ),
        )
    with pytest.raises(NarrativeUnavailable):
        export.build_display_snapshot(
            result,
            model="remote:model" if mutation == "model" else "qwen3:4b",
            generated_at=datetime(2026, 1, 2)
            if mutation == "time"
            else datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_atomic_export_never_implicitly_replaces_old_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "snapshot.json"
    monkeypatch.setattr(export, "_SNAPSHOT_PATH", target)
    target.write_text("null\n")
    export.write_mobile_snapshot(snapshot())
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        export.write_mobile_snapshot(snapshot())
    assert target.read_bytes() == original
    export.write_mobile_snapshot(snapshot(), replace_existing=True)
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]


def test_cli_requires_both_flags_and_failure_keeps_previous_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "snapshot.json"
    target.write_text("OLD SNAPSHOT")
    monkeypatch.setattr(export, "_SNAPSHOT_PATH", target)
    call = AsyncMock(
        return_value=replace(
            valid_result(),
            status="unavailable",
            narrative=None,
            unavailable_reason="provider_timeout",
        )
    )
    monkeypatch.setattr(export, "run_synthetic_ollama_smoke_test", call)
    for flags in (
        [],
        ["--allow-ollama-request"],
        ["--write-mobile-snapshot"],
        ["--allow-ollama-request", "--write-mobile-snapshot"],
    ):
        monkeypatch.setattr(sys, "argv", ["snapshot", *flags])
        assert export.main() == 1
        call.assert_not_called()
    monkeypatch.setattr(
        sys,
        "argv",
        ["snapshot", "--allow-ollama-request", "--write-mobile-snapshot", "--replace-existing"],
    )
    assert export.main() == 1
    assert target.read_text() == "OLD SNAPSHOT"
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["written"] is False
    call.assert_awaited_once_with(authorized=True)


def test_cli_success_exports_only_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "snapshot.json"
    monkeypatch.setattr(export, "_SNAPSHOT_PATH", target)
    monkeypatch.setattr(
        export, "run_synthetic_ollama_smoke_test", AsyncMock(return_value=valid_result())
    )
    monkeypatch.setattr(
        sys, "argv", ["snapshot", "--allow-ollama-request", "--write-mobile-snapshot"]
    )
    monkeypatch.setenv("OLLAMA_REPORT_MODEL", "qwen3:4b")
    assert export.main() == 0
    assert json.loads(target.read_text())["validated"] is True
    assert json.loads(capsys.readouterr().out)["written"] is True


def test_export_has_no_database_router_or_production_importers() -> None:
    path = Path(export.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        any(part in value for part in ("sqlalchemy", "fastapi", "app.db", "consent", "auth"))
        for value in imports
    )
    for other in path.parents[2].rglob("*.py"):
        if other != path:
            assert "local_report_snapshot" not in other.read_text(encoding="utf-8")
