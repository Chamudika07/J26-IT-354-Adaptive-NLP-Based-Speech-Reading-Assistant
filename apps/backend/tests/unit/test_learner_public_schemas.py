from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.learners.schemas import LearnerPreferenceUpdate


@pytest.mark.parametrize(
    "field,value",
    [
        ("preferred_language_tag", ""),
        ("preferred_language_tag", "  "),
        ("preferred_language_tag", "x" * 36),
        ("preferred_language_tag", 15),
        ("text_scale", True),
        ("text_scale", "NaN"),
        ("text_scale", "Infinity"),
        ("text_scale", "0.74"),
        ("text_scale", "3.01"),
        ("text_scale", "1.251"),
        ("text_scale", [1]),
        ("text_scale", {}),
        ("text_scale", "not-a-number"),
        ("line_spacing", False),
        ("line_spacing", "0.99"),
        ("line_spacing", "3.01"),
        ("line_spacing", "1.111"),
        ("line_spacing", "-Infinity"),
        ("reduce_motion", "false"),
        ("reduce_motion", "true"),
        ("reduce_motion", 0),
        ("reduce_motion", 1),
        ("reduce_motion", []),
        ("theme", "invalid"),
        ("row_version", True),
        ("row_version", "1"),
        ("row_version", 1.0),
        ("row_version", -1),
        ("row_version", None),
    ],
)
def test_invalid_public_preference_input(field, value):
    with pytest.raises(ValidationError):
        LearnerPreferenceUpdate.model_validate({"row_version": 0, "theme": "light", field: value})


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "learner_id",
        "updated_by_user_id",
        "created_at",
        "updated_at",
        "display_name",
        "age_band",
        "grade_level",
        "learner_user_id",
        "created_by_user_id",
        "archived_at",
        "roles",
        "relationship",
        "consent_records",
    ],
)
def test_non_preference_fields_forbidden(field):
    with pytest.raises(ValidationError):
        LearnerPreferenceUpdate.model_validate({"row_version": 0, field: None})


@pytest.mark.parametrize("payload", [{}, {"row_version": 0}, {"theme": "light"}])
def test_version_and_at_least_one_preference_required(payload):
    with pytest.raises(ValidationError):
        LearnerPreferenceUpdate.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"text_scale": "0.75"},
        {"text_scale": 3},
        {"text_scale": 1.25},
        {"line_spacing": "1.00"},
        {"line_spacing": 3.0},
        {"reduce_motion": False},
        {"reduce_motion": True},
        {"theme": "high_contrast"},
        {"preferred_language_tag": "  si-LK  "},
        {"text_scale": None},
    ],
)
def test_valid_values_and_patch_field_tracking(payload):
    parsed = LearnerPreferenceUpdate.model_validate({"row_version": 1, **payload})
    assert set(parsed.model_dump(exclude_unset=True)) == {"row_version", *payload}
    if "preferred_language_tag" in payload:
        assert parsed.preferred_language_tag == "si-LK"
    if parsed.text_scale is not None:
        assert isinstance(parsed.text_scale, Decimal)


def test_explicit_null_survives_while_omission_does_not():
    parsed = LearnerPreferenceUpdate(row_version=1, theme=None)
    assert parsed.model_dump(exclude_unset=True) == {"row_version": 1, "theme": None}
