"""Render stored evidence; never rerun the current pipeline to read historical profiles."""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import UUID

from app.core.exceptions import SecurityError
from app.modules.reading_materials.models import ReadingMaterialProcessingRun
from app.modules.reading_materials.schemas import (
    LengthLoad,
    SentenceStructure,
    TextProfile,
    Vocabulary,
    WordFormCharacteristics,
)


def ratio(numerator: int, denominator: int) -> Decimal:
    if numerator < 0 or denominator <= 0:
        raise ValueError("Invalid measurements")
    with localcontext() as context:
        context.prec = 40
        return (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


def build(material_id: UUID, row: ReadingMaterialProcessingRun) -> TextProfile:
    # Dispatch by immutable profile version, independently of the currently active pipeline.
    if row.profile_schema_version != "reading-profile-v1" or row.status != "succeeded":
        raise SecurityError(503, "service_unavailable", "Service unavailable")
    assert row.finished_at is not None
    assert row.character_count is not None and row.word_count is not None
    assert row.unique_word_count is not None and row.sentence_count is not None
    assert row.total_word_letter_count is not None and row.max_word_letter_count is not None
    assert row.max_sentence_word_count is not None
    return TextProfile(
        material_id=material_id,
        revision_id=row.revision_id,
        processing_run_id=row.id,
        pipeline_version=row.pipeline_version,
        profile_schema_version=row.profile_schema_version,
        completed_at=row.finished_at,
        length_load=LengthLoad(
            character_count=row.character_count,
            word_count=row.word_count,
            sentence_count=row.sentence_count,
        ),
        word_form_characteristics=WordFormCharacteristics(
            unique_word_count=row.unique_word_count,
            average_word_length=ratio(row.total_word_letter_count, row.word_count),
            maximum_word_length=row.max_word_letter_count,
            lexical_diversity=ratio(row.unique_word_count, row.word_count),
        ),
        sentence_structure=SentenceStructure(
            average_sentence_length=ratio(row.word_count, row.sentence_count),
            maximum_sentence_length=row.max_sentence_word_count,
        ),
        vocabulary=Vocabulary(),
    )
