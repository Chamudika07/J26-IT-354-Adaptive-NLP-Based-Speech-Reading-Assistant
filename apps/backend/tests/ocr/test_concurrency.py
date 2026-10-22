"PostgreSQL concurrency checks for instructor OCR review decisions."

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier
from time import sleep
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.reading_materials.models import ReadingMaterialRevision
from app.modules.reading_materials.ocr import service
from app.modules.reading_materials.ocr.models import ExtractionReview
from app.modules.reading_materials.ocr.schemas import (
    Acceptance,
    Rejection,
    ReviewedPage,
    Submission,
)
from app.modules.reading_materials.pdf.models import Source
from tests.reading_materials.test_concurrency import wait_blocked

from .conftest import (
    check,
    finish,
    new_review,
    new_run,
    new_source,
    ocr_values,
)

pytestmark = pytest.mark.integration


def prepared_review(
    engine,
    learner: UUID,
    principal: Principal,
    *,
    submitted: bool = True,
) -> tuple[UUID, UUID, UUID, int]:
    with Session(engine) as db:
        source = new_source(
            db,
            principal.user_id,
            learner,
        )

        parent = new_run(
            db,
            source,
            principal.user_id,
        )
        finish(db, parent)
        check(db)

        run = new_run(
            db,
            source,
            principal.user_id,
            **ocr_values(db, parent),
        )
        finish(
            db,
            run,
            "review_required",
            "Raw words.",
        )

        review = new_review(db, run)
        check(db)

        source_id = source.id
        run_id = run.id
        review_id = review.id

        db.commit()

        version = 1

        if submitted:
            result = service.submit(
                db,
                principal,
                learner,
                source_id,
                run_id,
                review_id,
                Submission(
                    row_version=1,
                    pages=[
                        ReviewedPage(
                            page_number=1,
                            text="Reviewed words.",
                            acknowledged=True,
                        )
                    ],
                ),
            )

            version = result.row_version

    return source_id, run_id, review_id, version


def revision_count(db: Session, run_id: UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ReadingMaterialRevision)
        .where(ReadingMaterialRevision.extraction_run_id == run_id)
    )


def test_duplicate_concurrent_accept_creates_one_revision(
    postgres_engine,
    context,
):
    learner, _, _, actors, _ = context

    source, run, review, version = prepared_review(
        postgres_engine,
        learner,
        actors[0],
    )

    request = Acceptance(
        row_version=version,
        decision_request_id=uuid4(),
    )

    barrier = Barrier(2)

    def accept_once():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='8s'"))

            barrier.wait(timeout=10)

            result = service.accept(
                db,
                actors[0],
                learner,
                source,
                run,
                review,
                request,
            )

            return (
                result.status,
                result.accepted_revision_id,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept_once) for _ in range(2)]

        values = [future.result(timeout=15) for future in futures]

    assert all(status == "accepted" for status, _ in values)

    assert values[0][1] == values[1][1]

    with Session(postgres_engine) as db:
        assert revision_count(db, run) == 1


def test_concurrent_accept_reject_has_one_terminal_decision(
    postgres_engine,
    context,
):
    learner, _, _, actors, _ = context

    source, run, review, version = prepared_review(
        postgres_engine,
        learner,
        actors[0],
    )

    barrier = Barrier(2)

    def decide(kind: str):
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='8s'"))

            barrier.wait(timeout=10)

            try:
                if kind == "accept":
                    result = service.accept(
                        db,
                        actors[0],
                        learner,
                        source,
                        run,
                        review,
                        Acceptance(
                            row_version=version,
                            decision_request_id=uuid4(),
                        ),
                    )
                else:
                    result = service.reject(
                        db,
                        actors[0],
                        learner,
                        source,
                        run,
                        review,
                        Rejection(
                            row_version=version,
                            decision_request_id=uuid4(),
                            reason="unusable_text",
                        ),
                    )

                return result.status

            except SecurityError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(decide, "accept"),
            pool.submit(decide, "reject"),
        ]

        outcomes = [future.result(timeout=15) for future in futures]

    assert outcomes.count("review_state_conflict") == 1

    terminal = next(value for value in outcomes if value != "review_state_conflict")

    assert terminal in {
        "accepted",
        "rejected",
    }

    with Session(postgres_engine) as db:
        review_row = db.get(
            ExtractionReview,
            review,
        )

        assert review_row.status == terminal

        assert revision_count(
            db,
            run,
        ) == (1 if terminal == "accepted" else 0)


@pytest.mark.parametrize(
    "context",
    [4],
    indirect=True,
)
def test_authorization_expiry_after_source_lock_wait(
    postgres_engine,
    context,
):
    learner, _, _, actors, expiry = context

    source, run, _, _ = prepared_review(
        postgres_engine,
        learner,
        actors[0],
        submitted=False,
    )

    pids: Queue[int] = Queue()

    def obtain_after_wait():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='8s'"))

            pids.put(db.scalar(text("SELECT pg_backend_pid()")))

            try:
                service.obtain(
                    db,
                    actors[0],
                    learner,
                    source,
                    run,
                )
                return "unexpected_success"

            except SecurityError as exc:
                return exc.code

    with (
        Session(postgres_engine) as blocker,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        blocker.scalar(select(Source).where(Source.id == source).with_for_update())

        future = pool.submit(obtain_after_wait)

        wait_blocked(
            blocker,
            pids.get(timeout=5),
        )

        while service.materials.now(blocker) <= expiry:
            sleep(0.02)

        blocker.commit()

        assert future.result(timeout=10) == "not_found"
