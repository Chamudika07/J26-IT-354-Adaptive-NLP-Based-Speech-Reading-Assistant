# Component 4 production integration handoff

**Component:** Transparent Learner Model & Adaptive Learning Analytics

**Status:** Integration proposal; no team approvals are recorded by this document

**Scope:** Backend reading-session ingestion, educational dashboards, advisory adaptation,
generated client, and Expo mobile integration

## Status language

- **Implemented** means the behavior exists in source and has automated test coverage.
- **Inactive** means code exists but is not reachable through a registered production route.
- **Draft** means a proposed integration contract that requires owner review.
- **Blocked** means activation must wait for an approved dependency or policy decision.

## 1. Current implementation and inactive boundaries

| Capability | Status | Evidence and boundary |
| --- | --- | --- |
| Reading-session validation, metric calculation, idempotency, authorization, and consent hook | Implemented internally | `ReadingSessionIngest` and `ingest_reading_session`; no Component 4 HTTP route is registered. |
| Learner-scoped bounded history | Implemented internally | Repository query enforces learner ID, half-open UTC window, stable ordering, and complete-result overflow failure. |
| Longitudinal analytics | Implemented | Pure, learner-free calculations partition by task type, difficulty tier, and observed support mode. |
| Learner, guardian, and educator projections | Implemented internally | Fixed, role-specific disclosure allowlists; experimental engagement is excluded. |
| Reporting request validation and adapters | Inactive | `ReportingRequest` and private adapters exist, but `learner_modelling/router.py` remains empty. |
| Adaptation engine | Implemented as pure advisory logic | Deterministic rules always return `is_advisory=True` and `safe_to_apply_automatically=False`. |
| Completed-session adaptation evidence | Implemented as pure preparation | Bounded historical records are validated, non-completed sessions are excluded, and duplicate identities fail closed. |
| Decision snapshots | Implemented as typed, immutable contracts | No persistence table, migration, service, or endpoint exists. |
| Expo dashboards | Implemented as a development preview | Deterministic synthetic data only; the live provider always returns an unavailable error and never falls back to demo data. |
| Generated TypeScript API client | Blocked | `packages/api-client` is a placeholder; no generated schemas or client exist. |

Relevant source:

- [`learner_modelling/service.py`](../apps/backend/app/modules/learner_modelling/service.py)
- [`learner_modelling/historical.py`](../apps/backend/app/modules/learner_modelling/historical.py)
- [`learner_modelling/repository.py`](../apps/backend/app/modules/learner_modelling/repository.py)
- [`learner_modelling/dashboard_projections.py`](../apps/backend/app/modules/learner_modelling/dashboard_projections.py)
- [`learner_modelling/api_contracts.py`](../apps/backend/app/modules/learner_modelling/api_contracts.py)
- [`learner_modelling/api_adapters.py`](../apps/backend/app/modules/learner_modelling/api_adapters.py)
- [`learner_modelling/adaptation_mapping.py`](../apps/backend/app/modules/learner_modelling/adaptation_mapping.py)
- [`learner_modelling/adaptation.py`](../apps/backend/app/modules/learner_modelling/adaptation.py)
- [`learner_modelling/decision_snapshots.py`](../apps/backend/app/modules/learner_modelling/decision_snapshots.py)
- [`mobile dashboardProvider.ts`](../apps/mobile/src/features/learnerModelling/data/dashboardProvider.ts)

## 2. Reading and speech telemetry producer contract

The reading/speech producer owner must submit one validated `ReadingSessionIngest` for
each logical session. The producer must:

- Generate a stable `client_session_id` and reuse it only for an exact retry of the
  same logical session. A changed payload with the same ID is a conflict.
- Provide timezone-aware session start/end timestamps with end at or after start.
- Provide nonnegative word, duration, pause, replay, and hesitation counts; correct
  words cannot exceed attempted words, active duration cannot exceed total duration,
  and pause duration cannot exceed total duration.
- Provide the observed task type, difficulty tier, support mode, and completion state.
  These values must describe the session that occurred, not a desired dashboard or
  adaptation outcome.
- Use `null` for measurements that were not collected. Missing data must not be sent as
  zero or inferred after the event.
- Avoid raw audio, document text, names, diagnoses, or other unnecessary identifying
  data in telemetry and logs.

**Owner:** Reading/speech producer owner.

**Acceptance criteria:** Contract tests against `ReadingSessionIngest`; exact-retry and
conflicting-retry tests; UTC tests; missing-telemetry tests; and documented provenance
for each produced metric.

## 3. Production `learning_support` consent contract

Component 4 currently expects this public callback:

```python
ConsentChecker = Callable[[Session, UUID, str], None]
```

The caller passes the shared database session, exact learner UUID, and purpose code
`learning_support`. Success returns `None`. Missing, declined, withdrawn, stale, or
otherwise invalid consent must raise a sanitized `SecurityError`. Unexpected internal
failures must not expose consent evidence or learner identifiers. Omitting the callback
must continue to fail closed.

**Blocked decisions for the Learners/Consent owner:**

1. Which guardian-consent and learner-assent records are required by age/context.
2. Which notice versions remain valid and how superseded notices are handled.
3. Whether evaluation locks consent rows or uses another method to prevent a concurrent
   withdrawal from racing history retrieval or ingestion.
4. Whether withdrawal stops only future collection/display or also triggers retention,
   erasure, or research-withdrawal workflows for existing data.
5. Stable sanitized error codes for absent, declined, withdrawn, stale, and temporarily
   unavailable consent.

**Acceptance criteria:** A public Learners-owned evaluator; denial and withdrawal tests;
concurrency tests; purpose-code tests; sanitized-error tests; and proof that Component 4
does not query consent tables directly.

## 4. Authorization and disclosure mappings

The following mappings exist as fixed internal candidates and require explicit approval
before HTTP activation:

| Use case | Action | Required access path | Status |
| --- | --- | --- | --- |
| Learner progress | `READ_EDUCATIONAL_SUMMARY` | `self` | Needs approval |
| Guardian summary | `READ_GUARDIAN_SUMMARY` | `guardian` | Needs approval |
| Educator analytics | `READ_EDUCATIONAL_SUMMARY` | `educator` | Needs approval, including detailed metric disclosure |
| Reading-session ingestion | `PERFORM_LEARNING_INTERACTION` | Determined by existing Learners authorization | Implemented internally; HTTP use unapproved |
| Adaptation recommendation | Undecided | Undecided | Blocked |

Clients must never choose the action, access path, consent result, or projection type.
The route selects a fixed service, and the backend verifies that the returned grant
matches the authenticated principal, requested learner, expected action, and expected
access path before consent or history access.

**Owner:** Auth/Learners authorization owner with privacy/disclosure approval from the
team lead or research supervisor.

**Acceptance criteria:** Approved matrix, role/grant integration tests, revocation and
expiry tests, cross-learner denial tests, and confirmation of educator-visible fields.

## 5. Draft HTTP contracts

All routes below are **DRAFT and unregistered**. Final names, rate limits, response
status codes, and disclosure fields require API/security review.

### DRAFT ingestion

`POST /api/v1/learner-modelling/reading-sessions`

- Request: existing `ReadingSessionIngest`.
- Authentication: shared authenticated `Principal` dependency.
- Authorization: `PERFORM_LEARNING_INTERACTION` for the payload learner.
- Consent: active `learning_support`, evaluated before idempotency lookup or write.
- Response: a minimized response derived from `ReadingSessionResponse`; whether the
  request digest and all calculated fields may be disclosed needs review.
- Idempotency: identical retry returns the existing record; conflicting retry maps to
  sanitized `409 digest_conflict`.
- Transaction: existing service owns its nested savepoint behavior; the HTTP layer must
  follow the repository's shared transaction convention.

### DRAFT dashboards

| Route | Fixed response |
| --- | --- |
| `GET /api/v1/learner-modelling/learners/{learner_id}/progress` | `LearnerProgressProjection` |
| `GET /api/v1/learner-modelling/learners/{learner_id}/guardian-summary` | `GuardianSummaryProjection` |
| `GET /api/v1/learner-modelling/learners/{learner_id}/educator-analytics` | `EducatorAnalyticsProjection` |

Each draft GET accepts timezone-aware `start_at_utc` and `end_at_utc`. The existing
`session_limit` is bounded by trusted server policy; whether clients may request a
smaller value remains an API decision. Responses must use `Cache-Control: no-store`.

Proposed sanitized mappings:

- `401 authentication_required`: no active authenticated principal.
- `404 not_found`: unauthorized or unavailable learner without relationship disclosure.
- `403 consent_required`: approved consent evaluator denies processing.
- `422 validation_error`: invalid UUID or reporting window.
- `503 service_unavailable`: result overflow, stored-data integrity failure, or
  unexpected consent-service failure.

Rate limiting, audit events, safe log fields, request correlation, and exact response
status behavior remain unapproved. No adaptation endpoint should be proposed until the
settings and partition policies in section 7 are approved.

## 6. Authentication and generated-client dependencies

The HTTP layer must use the existing shared authentication dependency to produce a
current `Principal`; it must not accept roles or access paths from request data. Mobile
session credentials require platform-backed secure storage and must never be placed in
plain AsyncStorage, source files, logs, or generated code.

After approved routes and OpenAPI contracts are stable, the API-client owner must
generate the TypeScript client in `packages/api-client`. Handwritten mobile copies of
Pydantic schemas are not authoritative. Generation must preserve separate learner,
guardian, and educator response types and sanitized error types.

**Acceptance criteria:** Reproducible generation command, clean regeneration diff,
authentication injection outside generated files, no embedded credentials, and mobile
tests proving that role/action/access-path/consent values cannot be supplied by UI data.

## 7. Adaptation settings and partition decisions

`LearnerReadingSupportSettings` contains the fields required to build
`SupportPreferences`, plus support mode, default difficulty, and manual-lock state.
No approved repository/service read contract currently supplies that state to the
adaptation mapper.

The Component 4 and database/security owners must decide:

1. Whether a missing settings row is an error, an explicit no-recommendation state, or
   is created by a separately authorized workflow. The recommendation service must not
   invent defaults.
2. How current settings are read consistently with authorization, consent, and history;
   including required lock order or snapshot/version checks.
3. How ORM decimals and booleans map into the pure `SupportPreferences` contract.
4. Which task type is eligible when history has several task partitions.
5. Whether partition selection uses current configured difficulty/support, the latest
   completed session context, or another approved deterministic rule.
6. What happens when the selected partition has no completed sessions or insufficient
   measurements.
7. Which authorization action/access path permits viewing an adaptation recommendation.

Partition selection must be server-owned. A client must not choose an authorization
policy, override consent, select a more favorable evidence partition, or assert manual
lock state.

**Acceptance criteria:** Approved deterministic policy; Component 4 repository read;
missing/corrupt/concurrent-settings tests; authorization-before-consent-before-history
ordering tests; completed-only evidence tests; and proof of zero settings writes.

## 8. Advisory recommendations and decision history

Every recommendation must be displayed as experimental educational guidance. It must
include its evidence limitations and non-clinical disclaimer. No recommendation may
change difficulty, support mode, or learner settings without a separate authorized
human action. `safe_to_apply_automatically=False` is mandatory.

The immutable snapshot contract can reproduce the evidence, thresholds, rule version,
and recommendation, but persistence is **not approved**. Before proposing migration
`0007`, the team must approve:

- Purpose and lawful/consented basis for persistence.
- Record creator and authorized readers.
- Idempotency key and relationship to reading sessions.
- Separation of recommendation generation from confirmed application.
- Retention, withdrawal, erasure, research export, and audit requirements.
- Whether explanations may be shown historically to each role.

Automatic recommendation application remains out of scope.

## 9. Expo mobile integration

The Expo SDK 57 app currently uses a Component 4 provider interface with three
role-specific methods. Demo mode is explicitly labeled, deterministic, and offline.
The inactive live provider always reports temporary unavailability and does not fall
back to synthetic data.

After endpoint and generated-client approval, Component 4 may implement a live provider
inside `apps/mobile/src/features/learnerModelling/`. It must consume generated types,
preserve the three role-specific projections, map only approved sanitized failures, and
never accept authorization actions, access paths, or consent decisions from the UI.

Integrating screens into production navigation, authentication state, learner selection,
and secure token storage changes shared mobile architecture and requires coordination
with the mobile/Auth owners. The preview role switcher must not become a production role
or permission selector.

## 10. Security, privacy, and reporting limits

- Candidate limits are a maximum 90-day half-open UTC window and 1,000 sessions. They
  are implemented as internal bounds but are not approved product policy.
- Historical overflow fails instead of returning partial, potentially misleading data.
- Every history query includes the authorized learner UUID and deterministic timestamp/
  UUID ordering.
- Projections contain no learner name, raw audio, document content, diagnosis, or session
  identifier. Experimental engagement is excluded from all initial dashboards.
- Missing values remain missing and are reported; they are never coerced to zero.
- Logs must exclude tokens, consent evidence, learner content, complete settings, SQL
  details, and raw request/response bodies.
- Dashboard and recommendation responses require `Cache-Control: no-store`; mobile
  caching and offline retention require separate privacy review.
- Production rate limits, retention periods, deletion behavior, audit events, and
  operational monitoring remain decisions for security/privacy owners.

## 11. Owners, acceptance criteria, and dependency order

| Order | Owner role | Required delivery | Acceptance gate |
| --- | --- | --- | --- |
| 1 | Team lead/research supervisor | Approve disclosure matrix, educational wording, reporting limits, and adaptation partition policy | Written decision with version/date |
| 2 | Learners/Consent owner | Public `learning_support` evaluator and withdrawal/concurrency semantics | Unit and disposable-database integration tests |
| 3 | Auth/Learners authorization owner | Approve actions/access paths for dashboards, ingestion, and recommendations | Cross-role, revocation, expiry, and cross-learner tests |
| 4 | Reading/speech producer owner | Produce validated, minimal, versioned session telemetry | Contract, retry, missing-data, and provenance tests |
| 5 | Component 4 owner | Add authoritative settings read and one orchestration path using existing security ordering | Pure and mocked orchestration tests; no writes |
| 6 | API/security owner | Approve and register minimal routes, errors, no-store headers, logs, and rate limits | HTTP security tests and OpenAPI review |
| 7 | API-client owner | Generate TypeScript client from approved OpenAPI | Reproducible clean generation |
| 8 | Mobile/Auth owners | Implement secure authenticated live provider and shared navigation | No demo fallback; device and failure-state tests |
| 9 | Database/security owner | Run disposable PostgreSQL integration/concurrency tests | Exclusive `_test` database and reset guard |
| 10 | Privacy/research owners | Decide decision-history persistence and research export | Separate migration/data-governance approval |

No later step should bypass an earlier acceptance gate.

## 12. Mobile testing and dependency audit

The repository configures Expo SDK 57, React Native, TypeScript, iOS identifiers, and an
Android package. Before production integration, record successful checks for both iOS
and Android:

- Fresh frozen-lockfile install under the documented Node 22/Yarn 1 environment.
- TypeScript, ESLint, Jest, Expo public configuration, `expo install --check`, and
  `expo-doctor`.
- Android emulator plus at least one physical Android device where available.
- iOS simulator/build validation and repeatable physical-device evidence. A working
  preview report alone does not validate authentication or live networking.
- Development-build testing for secure storage, TLS failures, token expiry, consent
  withdrawal, authorization loss, offline behavior, and no live-to-demo fallback.

The lockfile includes transitive packages previously identified for audit review,
including `node-forge`, `braces`, `uuid`, and `sprintf-js`. Their exact dependency
chains, patched versions, development/runtime reachability, and Expo SDK compatibility
must be documented before remediation. Do not apply blind upgrades or claim mobile
runtime exposure without bundle/dependency evidence.

## Activation checklist

- [ ] Disclosure and adaptation policies approved.
- [ ] Production consent evaluator approved and integrated.
- [ ] Authorization matrix approved.
- [ ] Telemetry producer contract verified.
- [ ] Authoritative settings and partition policy implemented.
- [ ] Internal adaptation orchestration remains advisory and read-only.
- [ ] HTTP routes reviewed, tested, and explicitly registered.
- [ ] Generated client produced from approved OpenAPI.
- [ ] Expo live provider uses generated types and secure authentication.
- [ ] Disposable PostgreSQL integration and concurrency tests pass.
- [ ] Android and iOS device evidence recorded.
- [ ] Dependency advisories reviewed with runtime-reachability evidence.
- [ ] Optional decision-history persistence separately approved.
