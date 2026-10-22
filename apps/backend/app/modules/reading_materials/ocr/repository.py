"""Scoped OCR persistence; never commits."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reading_materials.ocr.models import ExtractionReview, ExtractionReviewPage
from app.modules.reading_materials.pdf.models import ExtractionRun


def run(db: Session, source: UUID, identity: UUID) -> ExtractionRun | None:
    return db.scalar(
        select(ExtractionRun)
        .where(ExtractionRun.id == identity, ExtractionRun.source_id == source)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def review(db: Session, run_id: UUID) -> ExtractionReview | None:
    return db.scalar(
        select(ExtractionReview)
        .where(ExtractionReview.extraction_run_id == run_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def pages(db: Session, review_id: UUID) -> list[ExtractionReviewPage]:
    return list(
        db.scalars(
            select(ExtractionReviewPage)
            .where(ExtractionReviewPage.review_id == review_id)
            .order_by(ExtractionReviewPage.page_number)
        )
    )


def decision(db: Session, actor: UUID, request: UUID) -> ExtractionReview | None:
    return db.scalar(
        select(ExtractionReview).where(
            ExtractionReview.decided_by == actor, ExtractionReview.decision_request_id == request
        )
    )
