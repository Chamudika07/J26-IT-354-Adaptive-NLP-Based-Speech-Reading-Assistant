import ast
import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import DateTime, Table, UniqueConstraint, Uuid

from app.modules.learner_modelling.analytics import SessionTelemetry
from app.modules.learner_modelling.models import (
    LearnerReadingSupportSettings,
    ReadingSession,
)


def _compute_canonical_digest(payload: dict[str, object]) -> str:
    """Compute deterministic SHA-256 digest of canonically serialized JSON payload."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def test_reading_session_table_structure_and_constraints() -> None:
    table: Table = ReadingSession.__table__  # type: ignore[assignment]
    assert table.name == "reading_sessions"
    assert "id" in table.c
    assert isinstance(table.c.id.type, Uuid)
    assert table.c.id.primary_key

    # Required columns
    assert isinstance(table.c.client_session_id.type, Uuid)
    assert not table.c.client_session_id.nullable
    assert not table.c.learner_id.nullable
    assert not table.c.session_start_time.nullable
    assert not table.c.session_end_time.nullable

    # Timezone-aware timestamps
    assert isinstance(table.c.session_start_time.type, DateTime)
    assert table.c.session_start_time.type.timezone
    assert isinstance(table.c.session_end_time.type, DateTime)
    assert table.c.session_end_time.type.timezone

    # Nullable document reference without FK
    assert "document_id" in table.c
    assert isinstance(table.c.document_id.type, Uuid)
    assert table.c.document_id.nullable
    assert len(table.c.document_id.foreign_keys) == 0

    # Nullable telemetry fields
    for field in ("hesitation_count", "total_pause_duration_ms", "pause_count", "replay_count"):
        assert table.c[field].nullable, f"{field} should be nullable to preserve missing data"

    # Named check constraints
    constraint_names = {c.name for c in table.constraints if c.name}
    assert "ck_reading_sessions_words_attempted_nonnegative" in constraint_names
    assert "ck_reading_sessions_words_correct_nonnegative" in constraint_names
    assert "ck_reading_sessions_words_correct_le_attempted" in constraint_names
    assert "ck_reading_sessions_active_duration_le_total" in constraint_names
    assert "ck_reading_sessions_session_time_order" in constraint_names
    assert "ck_reading_sessions_request_digest_format" in constraint_names

    # Idempotency unique constraint
    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    idempotency_uqs = [
        c
        for c in unique_constraints
        if {col.name for col in c.columns} == {"learner_id", "client_session_id"}
    ]
    assert len(idempotency_uqs) == 1
    assert idempotency_uqs[0].name == "uq_reading_sessions_client_session"


def test_learner_reading_support_settings_structure_and_constraints() -> None:
    table: Table = LearnerReadingSupportSettings.__table__  # type: ignore[assignment]
    assert table.name == "learner_reading_support_settings"
    assert "id" in table.c
    assert "learner_id" in table.c
    assert not table.c.learner_id.unique

    # Exactly one unique constraint exists on learner_id with the canonical name
    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    learner_uqs = [
        c for c in unique_constraints if [col.name for col in c.columns] == ["learner_id"]
    ]
    assert len(learner_uqs) == 1
    assert learner_uqs[0].name == "uq_learner_reading_support_settings_learner_id"

    constraint_names = {c.name for c in table.constraints if c.name}
    assert "ck_learner_reading_support_settings_support_mode_values" in constraint_names
    assert "ck_learner_reading_support_settings_default_difficulty_values" in constraint_names
    assert "ck_learner_reading_support_settings_simplification_level_range" in constraint_names
    assert "ck_learner_reading_support_settings_speech_rate_multiplier_range" in constraint_names
    assert "ck_learner_reading_support_settings_pause_threshold_range" in constraint_names


def test_reading_session_orm_compatibility_with_session_telemetry() -> None:
    """Verify ReadingSession model fields map cleanly to and from SessionTelemetry."""
    start_time = datetime(2026, 10, 12, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2026, 10, 12, 10, 5, 0, tzinfo=UTC)
    learner_id = uuid.uuid4()
    client_session_id = uuid.uuid4()

    canonical_payload = {
        "learner_id": str(learner_id),
        "client_session_id": str(client_session_id),
        "session_start_time": start_time.isoformat(),
        "session_end_time": end_time,
        "task_type": "independent_reading",
        "difficulty_tier": "intermediate",
        "support_mode": "adaptive",
        "completion_status": "completed",
        "words_attempted": 100,
        "words_correct": 92,
        "target_word_count": 100,
        "active_duration_ms": 240000,
        "total_duration_ms": 300000,
        "hesitation_count": 3,
        "total_pause_duration_ms": 40000,
        "pause_count": 4,
        "replay_count": 1,
    }
    digest = _compute_canonical_digest(canonical_payload)

    session_orm = ReadingSession(
        id=uuid.uuid4(),
        learner_id=learner_id,
        client_session_id=client_session_id,
        request_digest=digest,
        session_start_time=start_time,
        session_end_time=end_time,
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
        completion_status="completed",
        document_id=None,
        words_attempted=100,
        words_correct=92,
        target_word_count=100,
        active_duration_ms=240000,
        total_duration_ms=300000,
        hesitation_count=3,
        total_pause_duration_ms=40000,
        pause_count=4,
        replay_count=1,
        calculated_accuracy=Decimal("0.9200"),
        calculated_wpm=Decimal("25.00"),
        calculated_hesitation_rate=Decimal("0.0300"),
        calculated_engagement_score=Decimal("0.8500"),
        engagement_formula_version="v0.1-research-heuristic",
    )

    # Convert ReadingSession ORM instance to pure SessionTelemetry dataclass
    telemetry = SessionTelemetry(
        session_start_time=session_orm.session_start_time,
        words_attempted=session_orm.words_attempted,
        words_correct=session_orm.words_correct,
        target_word_count=session_orm.target_word_count,
        active_duration_ms=session_orm.active_duration_ms,
        total_duration_ms=session_orm.total_duration_ms,
        hesitation_count=session_orm.hesitation_count,
        total_pause_duration_ms=session_orm.total_pause_duration_ms,
        pause_count=session_orm.pause_count,
        completion_status=session_orm.completion_status,  # type: ignore[arg-type]
        session_id=str(session_orm.id),
        task_type=session_orm.task_type,
        difficulty_tier=session_orm.difficulty_tier,
        support_mode=session_orm.support_mode,
    )

    assert telemetry.session_start_time == start_time
    assert telemetry.session_id == str(session_orm.id)
    assert telemetry.words_attempted == 100
    assert telemetry.words_correct == 92
    assert telemetry.hesitation_count == 3
    assert telemetry.total_pause_duration_ms == 40000


def test_idempotency_digest_stability() -> None:
    """Verify canonical digest produces identical SHA-256 for identical inputs."""
    payload1 = {"learner_id": "11111111-1111-1111-1111-111111111111", "count": 5, "duration": 100}
    payload2 = {"duration": 100, "count": 5, "learner_id": "11111111-1111-1111-1111-111111111111"}
    assert _compute_canonical_digest(payload1) == _compute_canonical_digest(payload2)

    conflicting_payload = {
        "learner_id": "11111111-1111-1111-1111-111111111111",
        "count": 6,
        "duration": 100,
    }
    assert _compute_canonical_digest(payload1) != _compute_canonical_digest(conflicting_payload)


def test_orm_and_migration_constraints_and_indexes_match() -> None:
    """Verify all ORM constraint and index names match the Alembic 0006 migration."""
    backend_dir = Path(__file__).resolve().parents[2]
    mig_file = backend_dir / "alembic" / "versions" / "0006_learner_reading_sessions.py"
    source = mig_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    migration_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "name":
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        migration_names.add(kw.value.value)
                    elif (
                        isinstance(kw.value, ast.Call)
                        and isinstance(kw.value.func, ast.Attribute)
                        and kw.value.func.attr == "f"
                        and isinstance(kw.value.args[0], ast.Constant)
                    ):
                        migration_names.add(str(kw.value.args[0].value))
            if isinstance(node.func, ast.Attribute) and node.func.attr == "create_index":
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant):
                    migration_names.add(str(first_arg.value))
                elif isinstance(first_arg, ast.Call) and isinstance(
                    first_arg.args[0], ast.Constant
                ):
                    migration_names.add(str(first_arg.args[0].value))

    # All ORM constraints on ReadingSession and LearnerReadingSupportSettings must be in migration
    for cls in (ReadingSession, LearnerReadingSupportSettings):
        table = cls.__table__
        for constraint in table.constraints:
            if constraint.name:
                assert constraint.name in migration_names, (
                    f"ORM constraint '{constraint.name}' on {table.name} not found in migration"
                )
        for idx in table.indexes:
            if idx.name:
                assert idx.name in migration_names, (
                    f"ORM index '{idx.name}' on {table.name} not found in migration"
                )
