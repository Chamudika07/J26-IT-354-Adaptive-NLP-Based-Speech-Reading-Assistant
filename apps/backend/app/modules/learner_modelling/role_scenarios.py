"""Opt-in learner-free role artifacts. No database, endpoints, auth or AI calls."""

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.learner_modelling.adaptation_mapping import CompletedSessionEvidence
from app.modules.learner_modelling.connected_demo import (
    ConnectedPreview,
    SampleFile,
    build_connected_preview,
    build_connected_replay,
)
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    project_educator_analytics,
    project_guardian_summary,
)
from app.modules.learner_modelling.longitudinal import LongitudinalObservation, LongitudinalWindow


class _Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schemaVersion: Literal["role-scenario-v1"] = "role-scenario-v1"
    synthetic: Literal[True] = True
    scenarioId: str


class GuardianArtifact(_Artifact):
    role: Literal["guardian"] = "guardian"
    projection: GuardianSummaryProjection


class EducatorArtifact(_Artifact):
    role: Literal["educator"] = "educator"
    projection: EducatorAnalyticsProjection


def scenario_identifier(index: int, preview: ConnectedPreview) -> str:
    data = preview.model_dump(mode="json")
    return json.dumps(
        [
            index,
            preview.sourceDigest,
            data["reportingStartUtc"],
            data["reportingEndUtc"],
            preview.context.task,
            preview.context.tier,
            preview.context.mode,
            data["generatedAt"],
        ],
        separators=(",", ":"),
    )


def build_role_artifacts(
    raw: str, reference: ConnectedPreview
) -> tuple[tuple[GuardianArtifact, ...], tuple[EducatorArtifact, ...]]:
    """Use identical validated evidence, then each existing role allowlist."""
    window = LongitudinalWindow(
        start_at_utc=reference.reportingStartUtc, end_at_utc=reference.reportingEndUtc
    )
    full = build_connected_preview(
        raw, window, reference.context, generated_at=reference.generatedAt
    )
    if full != reference:
        raise ValueError("Input does not match selected synthetic reference")
    steps = build_connected_replay(
        raw, window, reference.context, generated_at=reference.generatedAt
    )
    selected = sorted(
        (
            r
            for r in SampleFile.model_validate_json(raw).records
            if r.completion == "completed"
            and window.start_at_utc <= r.start < window.end_at_utc
            and (r.task, r.tier, r.mode)
            == (reference.context.task, reference.context.tier, reference.context.mode)
        ),
        key=lambda r: (r.start, str(r.id)),
    )
    guardians = []
    educators = []
    for index, preview in [*enumerate(steps), (-1, full)]:
        records = selected if index == -1 else selected[:index]
        evidence = CompletedSessionEvidence.from_observations(
            [
                LongitudinalObservation.from_telemetry(
                    r.ingest().to_session_telemetry(session_id=str(r.id))
                )
                for r in records
            ],
            window,
        )
        identifier = scenario_identifier(index, preview)
        guardians.append(
            GuardianArtifact(
                scenarioId=identifier, projection=project_guardian_summary(evidence.report)
            )
        )
        educators.append(
            EducatorArtifact(
                scenarioId=identifier, projection=project_educator_analytics(evidence.report)
            )
        )
    return tuple(guardians), tuple(educators)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export synthetic role projections only")
    parser.add_argument("--development-synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    if not args.development_synthetic_only:
        parser.error("Explicit synthetic opt-in required")
    base = Path(__file__).resolve().parents[4] / "mobile/src/features/learnerModelling/preview"
    try:
        raw = (base / "connectedSessionInput.json").read_text(encoding="utf-8")
        reference = ConnectedPreview.model_validate_json(
            (base / "connectedSessionContract.json").read_text(encoding="utf-8")
        )
        guardian, educator = build_role_artifacts(raw, reference)
        # Validate every output before writing any file. Pins are demo integrity, not auth.
        outputs = {}
        for role, artifacts in (("guardian", guardian), ("educator", educator)):
            outputs[role] = "[" + ",".join(a.model_dump_json(indent=2) for a in artifacts) + "]\n"
        for role, payload in outputs.items():
            for suffix in ("Results", "Contract"):
                (base / f"{role}Scenario{suffix}.json").write_text(payload, encoding="utf-8")
    except Exception:
        parser.exit(2, "Synthetic role export rejected. Check matching source fixtures.\n")


if __name__ == "__main__":
    main()
