from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.auth.models import User
from app.modules.auth.schemas import UserRead
from app.modules.learners.schemas import LearnerPreferencesInput, LearnerProfileCreate


@pytest.mark.parametrize("age", [None, 9, 10, 11, 12])
@pytest.mark.parametrize("grade", [None, 3, 8])
def test_profile_accepts_approved_age_and_grade(age: int | None, grade: int | None) -> None:
    profile = LearnerProfileCreate(
        display_name="Synthetic learner", age_band=age, grade_level=grade
    )
    assert profile.age_band == age
    assert profile.grade_level == grade


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_band", 8),
        ("age_band", 13),
        ("age_band", True),
        ("age_band", "10"),
        ("grade_level", 2),
        ("grade_level", 9),
        ("grade_level", 4.5),
        ("display_name", "   "),
        ("date_of_birth", "2015-01-01"),
        ("national_id", "synthetic"),
        ("diagnosis", "synthetic"),
        ("home_address", "synthetic"),
        ("dyslexia_severity", "synthetic"),
        ("clinical_history", "synthetic"),
        ("created_by_user_id", str(uuid4())),
        ("learner_user_id", str(uuid4())),
    ],
)
def test_profile_rejects_invalid_or_unapproved_input(field: str, value: object) -> None:
    payload = {"display_name": "Synthetic", field: value}
    with pytest.raises(ValidationError):
        LearnerProfileCreate.model_validate(payload)


def test_user_projection_never_serializes_password_hash() -> None:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        login_handle="synthetic",
        status="disabled",
        password_hash="secret-marker",
        created_at=now,
        updated_at=now,
        row_version=1,
    )
    projection = UserRead.model_validate(user).model_dump_json()
    assert "password_hash" not in projection
    assert "secret-marker" not in projection


@pytest.mark.parametrize(
    "payload", [{"text_scale": 0.5}, {"line_spacing": 4}, {"theme": "unknown"}]
)
def test_preference_ranges(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LearnerPreferencesInput.model_validate(payload)
