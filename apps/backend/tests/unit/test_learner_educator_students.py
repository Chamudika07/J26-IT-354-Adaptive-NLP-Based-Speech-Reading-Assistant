import json
from pathlib import Path

import pytest

from app.modules.learner_modelling.educator_students import build_student_projections
from app.modules.learner_modelling.longitudinal import LongitudinalWindow

BASE = Path(__file__).resolve().parents[3] / "mobile/src/features/learnerModelling/preview"


def test_distinct_fictional_histories_are_projected_minimally_and_reproducibly() -> None:
    source = json.loads((BASE / "educatorStudentSources.json").read_text(encoding="utf-8"))
    window = LongitudinalWindow.model_validate(source["window"])
    projections = [build_student_projections(json.dumps(s), window) for s in source["students"]]
    assert [p.included_session_count for p in projections] == [6, 2]
    assert projections[0] != projections[1]
    assert {r["id"] for r in source["students"][0]["records"]}.isdisjoint(
        r["id"] for r in source["students"][1]["records"]
    )
    assert projections[0].partitions[0].metrics[0].evidence_sufficient
    assert not projections[1].partitions[0].metrics[0].evidence_sufficient
    assert projections[1].partitions[0].metrics[2].latest_value is None
    for suffix in ("Results", "Contract"):
        assert json.loads((BASE / f"educatorStudent{suffix}.json").read_text(encoding="utf-8")) == [
            p.model_dump(mode="json") for p in projections
        ]
    payload = json.dumps([p.model_dump(mode="json") for p in projections])
    for forbidden in ("learner_id", "engagement", "recommendation", "client_session_id"):
        assert forbidden not in payload
    raw = source["students"][0]
    assert (
        build_student_projections(
            json.dumps({**raw, "records": list(reversed(raw["records"]))}), window
        )
        == projections[0]
    )
    assert (
        build_student_projections(json.dumps({**raw, "records": []}), window).included_session_count
        == 0
    )


def test_invalid_and_duplicate_records_are_rejected() -> None:
    source = json.loads((BASE / "educatorStudentSources.json").read_text(encoding="utf-8"))
    window = LongitudinalWindow.model_validate(source["window"])
    raw = source["students"][0]
    for invalid in (
        {},
        {**raw, "synthetic": False},
        {**raw, "records": [raw["records"][0]] * 2},
        {**raw, "records": [{**raw["records"][0], "correct": 999}]},
    ):
        with pytest.raises(ValueError):
            build_student_projections(json.dumps(invalid), window)
