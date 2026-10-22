"""Explicit synthetic-only offline export. No router, database or mobile network bridge.

From apps/backend, after authorization:
    uv run --frozen python -m app.modules.learner_modelling.local_report_snapshot \
        --allow-ollama-request --write-mobile-snapshot
An existing nonempty snapshot requires --replace-existing. Failure leaves it untouched.
The mobile preview requires a separate development-only user opt-in on each screen visit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.learner_modelling.ollama_report_smoke import (
    _LOCAL_MODELS,
    run_synthetic_ollama_smoke_test,
)
from app.modules.learner_modelling.report_evidence import build_structured_report
from app.modules.learner_modelling.report_narrative import (
    NarrativeUnavailable,
    ReportGenerationResult,
    validate_narrative,
)
from app.modules.learner_modelling.report_synthetic import build_synthetic_projection

_MOBILE_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "mobile/src/features/learnerModelling/preview"
)
_SNAPSHOT_PATH = _MOBILE_DIRECTORY / "localReportSnapshot.json"


class LocalReportSnapshot(BaseModel):
    """Only approved display text; no identities, prompts, references or fingerprints."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schemaVersion: Literal["synthetic-local-report-v1"] = "synthetic-local-report-v1"
    synthetic: Literal[True] = True
    source: Literal["local-ollama"] = "local-ollama"
    validated: Literal[True] = True
    role: Literal["learner"] = "learner"
    model: str
    generatedAt: str
    reportingStartUtc: str
    reportingEndUtc: str
    statements: tuple[str, ...]


def build_display_snapshot(
    result: ReportGenerationResult, *, model: str, generated_at: datetime
) -> LocalReportSnapshot:
    """Revalidate against our own fixed learner fixture, never a caller's evidence."""
    expected = build_structured_report(build_synthetic_projection())
    if (
        result.status != "validated_narrative"
        or result.unavailable_reason is not None
        or result.narrative is None
        or result.factual_report != expected
        or model not in _LOCAL_MODELS
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        raise NarrativeUnavailable("invalid_narrative")
    draft = validate_narrative(expected.narrative_request, result.narrative.model_dump_json())
    period = expected.projection.reporting_period
    return LocalReportSnapshot(
        model=model,
        generatedAt=generated_at.astimezone(UTC).isoformat(timespec="seconds"),
        reportingStartUtc=period.start_at_utc.isoformat(),
        reportingEndUtc=period.end_at_utc.isoformat(),
        statements=tuple(item.text for item in draft.statements),
    )


def write_mobile_snapshot(snapshot: LocalReportSnapshot, *, replace_existing: bool = False) -> None:
    """Write atomically to one feature-owned path, preserving older snapshots on failure."""
    snapshot = LocalReportSnapshot.model_validate(snapshot.model_dump(mode="python"))
    timestamp = datetime.fromisoformat(snapshot.generatedAt)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Snapshot timestamp must include timezone")
    # Export only a display projection that still matches the fixed approved catalogue.
    expected = build_structured_report(build_synthetic_projection())
    if (
        snapshot.model not in _LOCAL_MODELS
        or sorted(snapshot.statements)
        != sorted(item.text for item in expected.narrative_request.approved_statements)
        or snapshot.reportingStartUtc
        != expected.projection.reporting_period.start_at_utc.isoformat()
        or snapshot.reportingEndUtc != expected.projection.reporting_period.end_at_utc.isoformat()
    ):
        raise ValueError("Snapshot is not the approved synthetic display projection")
    if _SNAPSHOT_PATH.exists() and not replace_existing:
        if _SNAPSHOT_PATH.read_text(encoding="utf-8").strip() != "null":
            raise FileExistsError("Explicit replacement required")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=_SNAPSHOT_PATH.parent, delete=False
        ) as handle:
            temporary = handle.name
            handle.write(snapshot.model_dump_json(indent=2) + "\n")
        os.replace(temporary, _SNAPSHOT_PATH)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one validated synthetic local AI snapshot")
    parser.add_argument("--allow-ollama-request", action="store_true")
    parser.add_argument("--write-mobile-snapshot", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()
    if not args.allow_ollama_request or not args.write_mobile_snapshot:
        print(json.dumps({"synthetic_only": True, "status": "disabled", "written": False}))
        return 1
    # Refuse overwrite before spending time on generation.
    if _SNAPSHOT_PATH.exists() and not args.replace_existing:
        if _SNAPSHOT_PATH.read_text(encoding="utf-8").strip() != "null":
            print(json.dumps({"status": "replacement_required", "written": False}))
            return 1
    result = asyncio.run(run_synthetic_ollama_smoke_test(authorized=True))
    if result.status != "validated_narrative":
        print(
            json.dumps(
                {
                    "status": result.status,
                    "reason": result.unavailable_reason,
                    "written": False,
                    "synthetic_only": True,
                }
            )
        )
        return 1
    try:
        snapshot = build_display_snapshot(
            result,
            model=os.environ.get("OLLAMA_REPORT_MODEL", "qwen3:4b"),
            generated_at=datetime.now(UTC),
        )
        write_mobile_snapshot(snapshot, replace_existing=args.replace_existing)
    except Exception:
        # Never print provider text, configuration, exception details or file contents.
        print(json.dumps({"status": "export_unavailable", "written": False}))
        return 1
    print(
        json.dumps(
            {
                "status": "validated_narrative",
                "written": True,
                "synthetic_only": True,
                "source": "local-ollama",
                "generatedAt": snapshot.generatedAt,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
