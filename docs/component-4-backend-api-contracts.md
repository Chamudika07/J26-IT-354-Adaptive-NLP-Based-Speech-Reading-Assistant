# Component 4 authenticated API contracts - Step 295

This document supersedes earlier handoff statements that the Component 4 router
is empty. No models, migrations, shared registration or mobile providers changed.
The existing `/api/v1/learner-modelling` registration now exposes:

| Method and relative path | Contract and existing policy |
| --- | --- |
| GET `/learners/{learner_id}/progress` | `LearnerProgressProjection`; educational-summary action with exact self access path |
| GET `/learners/{learner_id}/guardian-summary` | `GuardianSummaryProjection`; guardian-summary action with existing guardian relationship |
| GET `/learners/{learner_id}/educator-analytics` | `EducatorAnalyticsProjection`; educational-summary action with existing educator relationship |
| POST `/reading-sessions` | `ReadingSessionIngest`; protected-write authentication, learning-interaction authorization, consent, calculations and idempotency |

## Request, response and transaction behavior

Reporting requires timezone-aware `start_at_utc` and `end_at_utc` query parameters
and uses the existing half-open `[start, end)` convention. Maximum window is 90 days;
`session_limit` is 1-1,000 (default 1,000). Overflow refuses partial analytics. Dates
normalize to UTC. Clients cannot choose a grant, consent decision or projector.
Projection units remain `proportion`, `words_per_minute`, and
`hesitations_per_attempted_word`; mobile adapters must format percentages/per-100
rates without duplicating analytical rules. Empty evidence remains empty.

Ingestion returns only `{id, client_session_id, created}`: 201 for a new record,
200 for an identical retry and 409 for a conflicting retry. The HTTP layer validates
the receipt before committing the shared request session. Failures roll back when
that session closes. Internal digests, experimental engagement and unrestricted ORM
objects are excluded. Use the role-specific reporting routes to read analytics.
Successful responses and shared security/database/validation errors use no-store.
OpenAPI exposes separate response schemas and Bearer security for all four routes.

## Consent remains blocked

`get_learning_support_consent_checker` installs the existing deny-by-default
checker. An authenticated and learner-authorized request still receives 403
`consent_required` before history retrieval or ingestion until an approved public
evaluator exists. No environment flag or client field grants consent. Successful
HTTP tests override this dependency with **synthetic test consent only**.
Unexpected evaluator failures return sanitized 503.

Authorization uses the public Learners service and its existing relationship
records. Global role selection alone is not a learner grant. Unrelated/missing
relationships and mismatched role access paths return 404. Missing/invalid/expired
authentication returns 401. Invalid inputs return sanitized 422; database or
invalid historical evidence failures return sanitized 503.

Remaining team decisions: public active `learning_support` consent evaluation,
withdrawal/transaction locking semantics and confirmation of role-specific
disclosure policies. Do not query Consent tables to invent an evaluator. Shared
Auth/session and Learners relationship implementations are reused without edits.

## Exact remaining mobile integration work

- Home/Profile observations, Analytics, Guardian and Educator still use demo or
  prepared evidence. `data/dashboardProvider.ts` has no live network provider.
  After consent integration, add an authenticated provider that obtains authorized
  learner IDs from the shared Learners API, supplies reporting bounds, validates
  separate role responses, maps units/limitations to presentation types and handles
  401/403/404/422/503 without sample fallback. Never pass Learner responses to other
  roles or treat the demo switcher as authentication.
- Reading Results scenarios are not authoritative Speech telemetry. Finalize the
  upstream measurement mapping to `ReadingSessionIngest` before real submissions.
  Do not submit prepared scenarios as actual learner records. Re-fetch the same
  reporting window after successful ingestion; a receipt is not a dashboard.
- Identity/profile and accessibility preferences already have shared
  `/api/v1/learners` APIs. Do not duplicate their writes in Component 4 or confuse
  temporary demo identity with verified learner identity.
- Authoritative support-settings and recommendation routes remain unregistered:
  settings access/lock ownership and context-selection policy need approval.
  Accessibility preferences are not authoritative adaptive support settings.
  Feedback has no approved persisted session association/API.
- AI generation, class reports and PDFs are not new endpoints here. The independent
  Qwen3 snapshot, native PDF export and offline builders remain unchanged. A live
  AI endpoint needs consent, approved role evidence/provider policy and the existing
  factual validator. Deterministic analytics are not newly AI-generated reports.

## Verification scope

HTTP tests use real Component 4 services, analytics and role projectors with mocked
auth/repository boundaries and explicit synthetic consent. They do not rerun
PostgreSQL fixtures (which automatically migrate), access PostgreSQL or establish
end-to-end production/mobile readiness. The user's completed PostgreSQL tests are
separate from HTTP-layer verification. No dependencies, mobile files, teammate
modules, database models or migration files are changed by this step.
