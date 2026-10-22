"""Private support-settings retrieval foundation; no route or production security wiring.

This is NOT authentication, learner authorization or consent evaluation. A future
approved caller must perform all three before invoking this function in the shared
transaction. There is no approved action/access-path mapping or public consent
integration for these settings yet. Do not call this from a mobile/live provider.
"""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.modules.learner_modelling import repository
from app.modules.learner_modelling.models import LearnerReadingSupportSettings
from app.modules.learner_modelling.schemas import SupportSettingsRead


class InvalidSupportSettings(ValueError):
    def __init__(self) -> None:
        super().__init__("Stored support settings are invalid.")


class SupportSettingsUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("Support settings are unavailable.")


def _read_support_settings(db: Session, learner_id: UUID) -> SupportSettingsRead | None:
    """Read existing settings only. None means absent, never defaults or unavailable.

    Reads do not evaluate recommendation precedence or infer lock ownership.
    They preserve the stored fixed/manual/adaptive mode and global lock exactly.
    Errors contain no identities, SQL, settings values or exception details.
    """
    if type(learner_id) is not UUID:
        raise InvalidSupportSettings()
    try:
        row = repository.get_support_settings(db, learner_id)
    except MultipleResultsFound:
        raise InvalidSupportSettings() from None
    except Exception:
        raise SupportSettingsUnavailable() from None
    if row is None:
        return None
    try:
        if (
            not isinstance(row, LearnerReadingSupportSettings)
            or type(row.learner_id) is not UUID
            or row.learner_id != learner_id
        ):
            raise InvalidSupportSettings()
        return SupportSettingsRead.model_validate(
            {name: getattr(row, name) for name in SupportSettingsRead.model_fields}
        )
    except (ValidationError, ValueError, TypeError):
        raise InvalidSupportSettings() from None
    except Exception:
        raise SupportSettingsUnavailable() from None
