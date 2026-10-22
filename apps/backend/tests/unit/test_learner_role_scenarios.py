import json
from pathlib import Path

import pytest

from app.modules.learner_modelling.connected_demo import ConnectedPreview
from app.modules.learner_modelling.role_scenarios import build_role_artifacts

BASE = Path(__file__).resolve().parents[3] / "mobile/src/features/learnerModelling/preview"


def test_role_exports_match_selected_evidence_and_closed_projections() -> None:
    raw = (BASE / "connectedSessionInput.json").read_text(encoding="utf-8")
    reference = ConnectedPreview.model_validate_json(
        (BASE / "connectedSessionContract.json").read_text(encoding="utf-8")
    )
    guardian, educator = build_role_artifacts(raw, reference)
    learner_steps = json.loads((BASE / "connectedSessionReplay.json").read_text(encoding="utf-8"))
    assert len(guardian) == len(educator) == len(learner_steps) + 1
    for index, (g, e) in enumerate(zip(guardian, educator, strict=True)):
        count = reference.includedSessionCount if index == len(learner_steps) else index
        assert g.scenarioId == e.scenarioId
        assert g.projection.included_session_count == e.projection.included_session_count == count
        assert g.projection.reporting_period == e.projection.reporting_period
        assert g.projection.reporting_period.start_at_utc == reference.reportingStartUtc
        for payload in (g.model_dump_json(), e.model_dump_json()):
            for forbidden in (
                "experimentalEngagement",
                "engagement",
                "recommendation",
                "learner_id",
                '"settings"',
                '"history"',
                '"statements"',
            ):
                assert forbidden not in payload
        if count:
            learner = learner_steps[count]
            for metric, gm, em in zip(
                learner["metrics"],
                g.projection.contexts[0].metrics,
                e.projection.partitions[0].metrics,
                strict=True,
            ):
                assert gm.latest_value == em.latest_value
                assert str(gm.latest_value) == metric["latest_value"]
                assert gm.change_direction == em.change_direction == metric["change_direction"]
    for role, expected in (("guardian", guardian), ("educator", educator)):
        actual = json.loads((BASE / f"{role}ScenarioResults.json").read_text(encoding="utf-8"))
        assert actual == [a.model_dump(mode="json") for a in expected]
        assert actual == json.loads(
            (BASE / f"{role}ScenarioContract.json").read_text(encoding="utf-8")
        )


def test_role_export_rejects_mismatched_or_invalid_source() -> None:
    reference = ConnectedPreview.model_validate_json(
        (BASE / "connectedSessionContract.json").read_text(encoding="utf-8")
    )
    for raw in (
        "{}",
        "{invalid",
        '{"synthetic": false}',
        '{"version": 2, "synthetic": true, "verifiedTelemetry": false, "records": []}',
    ):
        with pytest.raises(ValueError):
            build_role_artifacts(raw, reference)
