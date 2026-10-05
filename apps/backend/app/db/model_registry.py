"""Explicit model discovery for the single Alembic metadata collection."""

from app.db.base import Base
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.modules.learner_modelling import models as learner_modelling_models  # noqa: F401
from app.modules.learners import models as learner_models  # noqa: F401
from app.modules.numeracy import models as numeracy_models  # noqa: F401
from app.modules.simplification import models as simplification_models  # noqa: F401
from app.modules.speech import models as speech_models  # noqa: F401

target_metadata = Base.metadata
