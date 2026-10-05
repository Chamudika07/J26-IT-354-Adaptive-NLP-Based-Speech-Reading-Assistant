"""Versioned API composition; only health and authentication expose endpoints."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.documents.router import router as documents_router
from app.modules.learner_modelling.router import router as learner_modelling_router
from app.modules.learners.router import router as learners_router
from app.modules.numeracy.router import router as numeracy_router
from app.modules.simplification.router import router as simplification_router
from app.modules.speech.router import router as speech_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(learners_router, prefix="/learners", tags=["learners"])
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(simplification_router, prefix="/simplification", tags=["simplification"])
router.include_router(speech_router, prefix="/speech", tags=["speech"])
router.include_router(
    learner_modelling_router, prefix="/learner-modelling", tags=["learner-modelling"]
)
router.include_router(numeracy_router, prefix="/numeracy", tags=["numeracy"])
