"""Offline fictional histories; no roster authorization, database or network access."""

import argparse
import json
from pathlib import Path

from app.modules.learner_modelling.adaptation_mapping import CompletedSessionEvidence
from app.modules.learner_modelling.connected_demo import SampleFile
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    project_educator_analytics,
)
from app.modules.learner_modelling.longitudinal import LongitudinalObservation, LongitudinalWindow


def build_student_projections(raw: str, window: LongitudinalWindow) -> EducatorAnalyticsProjection:
    """Only existing validated completed-session evidence may reach the role projector."""
    records = SampleFile.model_validate_json(raw).records
    evidence = CompletedSessionEvidence.from_observations(
        [
            LongitudinalObservation.from_telemetry(
                r.ingest().to_session_telemetry(session_id=str(r.id))
            )
            for r in records
            if r.completion == "completed"
        ],
        window,
    )
    return project_educator_analytics(evidence.report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export fictional Educator-only histories")
    parser.add_argument("--development-synthetic-only", action="store_true", required=True)
    parser.parse_args()
    base = Path(__file__).resolve().parents[4] / "mobile/src/features/learnerModelling/preview"
    source = json.loads((base / "educatorStudentSources.json").read_text(encoding="utf-8"))
    window = LongitudinalWindow.model_validate(source["window"])
    outputs = [
        build_student_projections(json.dumps(s), window).model_dump(mode="json")
        for s in source["students"]
    ]
    payload = json.dumps(outputs, indent=2) + "\n"
    for suffix in ("Results", "Contract"):
        (base / f"educatorStudent{suffix}.json").write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
