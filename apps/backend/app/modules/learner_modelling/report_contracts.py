"""Closed narrative contracts; no identities, settings, tools, or free-form conclusions.

This schema is an internal foundation, not an approved production API contract.
Schema compliance alone does not establish factual correctness. Every proposed
statement must also match the report's locally approved evidence catalogue.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ReportRole = Literal["learner", "guardian", "educator"]


class ReportContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReferencedStatement(ReportContract):
    evidence_ref: Annotated[str, Field(pattern=r"^e[0-9]{4}$")]
    text: Annotated[str, Field(min_length=1, max_length=1000)]


class NarrativeRequest(ReportContract):
    """Only server-built, privacy-minimized statement choices reach a provider."""

    schema_version: Literal["report-narrative-v1"]
    role: ReportRole
    report_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    approved_statements: Annotated[
        tuple[ReferencedStatement, ...], Field(min_length=1, max_length=1024)
    ]


class NarrativeDraft(ReportContract):
    """Provider may arrange approved statements, but may not introduce new prose."""

    schema_version: Literal["report-narrative-v1"]
    report_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    statements: Annotated[tuple[ReferencedStatement, ...], Field(min_length=1, max_length=1024)]
