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

## 13. STEP 170 source-verified real-data readiness review

This review records receiving-side readiness, not permission to activate anything.
No PostgreSQL or model service was contacted. Existing adapters are reused, not
reimplemented. Passing mocked tests is not evidence of teammate producer compatibility,
real authorization/consent evaluation, database concurrency or production readiness.

### Exact arrival path and current gap

The intended minimal path is:

1. Speech supplies authoritative measured counts, with an agreed word-alignment and
   hesitation definition. Adaptive Reading owns the actual session lifecycle and
   observed task/difficulty/support context. **This ownership split is a proposal for
   teammate approval, not an implemented event contract.**
2. One agreed session producer joins those measurements and context for the same
   learner and logical session. It builds the existing `ReadingSessionIngest`.
3. A future approved authenticated HTTP boundary, or an approved in-process service
   caller using the shared transaction, invokes `service.ingest_reading_session`.
   No event bus, queue consumer, Speech-to-Component-4 translator or production
   ingestion route currently implements steps 1â€“3. Do not create a second backend.
4. The existing service protects the Auth session, calls Learners authorization for
   `PERFORM_LEARNING_INTERACTION`, evaluates `learning_support` consent, computes its
   own digest/metrics, verifies the protected session and resolves exact retries.
   It writes only Component 4 tables and does not commit the outer transaction.
5. Reporting uses the existing private `api_adapters._read_learner_progress`,
   `_read_guardian_summary` and `_read_educator_analytics`, then the fixed service
   policy, consent check, bounded history, analytics and role projection.
6. `build_structured_report` can consume those projections. `generate_progress_report`
   defaults to an inactive narrative provider. Factual reporting readiness does not
   authorize live learner model processing, snapshot export or PDF export.

In the inspected source, Speech's `service.py`/`schemas.py` remain placeholders.
There is no dedicated Adaptive Reading backend module or approved public producer
output in this checkout. Exact real measurements therefore **cannot arrive yet**;
Component 4 has a receiving contract, not a verified upstream integration.

### Minimum producer delivery (existing schema, no new wire fields)

| Fields | Required delivery and semantics | Proposed accountable owner |
| --- | --- | --- |
| `learner_id` | Existing learner UUID; never a name/login or permission assertion. Backend independently authorizes it. | Session producer with Learners owner |
| `client_session_id` | Stable UUID for one logical finalized session; reuse unchanged only for exact retries. Changing payload under the same learner/session key causes `409 digest_conflict`. Component 4 assigns the stored row UUID separately. | Session lifecycle owner |
| `document_id` | Optional existing document UUID, otherwise null. Never transmit document text or invent a document identity. Whether a supplied document must be separately authorized/validated remains an agreed integration requirement. | Reading/Documents owners |
| `session_start_time`, `session_end_time` | Timezone-aware instants, end >= start. Canonical hashing normalizes equivalent instants to UTC. Define producer clocks, finalization and interrupted/offline-session behavior. | Session lifecycle owner |
| `task_type` | `independent_reading`, `assisted_read_aloud`, `guided_echo_reading` | Adaptive Reading owner |
| `difficulty_tier` | Observed `early`, `intermediate`, `advanced`, not a suggested next level | Adaptive Reading owner |
| `support_mode` | Observed `baseline_fixed`, `adaptive`, `manual_override`, not a proposed support change | Adaptive Reading owner |
| `completion_status` | `completed`, `abandoned`, `interrupted`; finalized state, not an inferred success score | Session lifecycle owner |
| `words_attempted`, `words_correct`, `target_word_count` | Required nonnegative counts; correct <= attempted. Agree tokenization, repetitions, omitted words, alignment and confidence treatment; recognizer output alone is not an approved accuracy count. | Speech + Reading owners |
| `active_duration_ms`, `total_duration_ms` | Required nonnegative milliseconds; active <= total. Define active-reading versus playback/paused/background time. Backend WPM uses attempted words / active minutes, not correct words. | Session lifecycle owner, Speech validation |
| `hesitation_count`, `total_pause_duration_ms`, `pause_count`, `replay_count` | Nullable nonnegative counters; unmeasured = null, measured none = zero. Pause duration <= total. Specify hesitation thresholds and replay/event ownership. | Speech/session owners |

The four context/completion fields currently have schema defaults. An approved
producer must nevertheless send all four explicitly so real observed context is not
silently replaced by scaffolding defaults. Required word counts/durations cannot be
null: when authoritative values are unavailable, do not send zero or fabricate them;
finalization/rejection policy needs agreement. Only the optional counters above may
represent unavailable measurement as null under the current receiving contract.

There is no accepted producer `event_id`, model version, confidence, raw transcript,
precomputed score or provenance field in this closed payload. `client_session_id` is
the current retry identity. Source/model/version provenance, any versioned envelope
and correction semantics must be designed with the producer owner before adding
fields; the canonical digest's `v1` is not a Speech model version. An updated
measurement after finalization is not an exact retry. Do not generate a fresh UUID
just to evade a conflict and count the same session twice.

### Auth, authorization and consent: existing contracts versus missing delivery

- **Auth exists:** `auth.dependencies.get_current_principal` / `Authenticated` call
  `auth.service.resolve_principal` and produce immutable `Principal` fields
  `user_id`, `login_handle`, `roles`, `session_id`, `authenticated_at`, `token_id`,
  `issued_at`, `expires_at`, `status`. Never construct a production principal from
  a client role switcher. Ingestion already uses `protect_principal_for_write` and
  `assert_protected_session_live`; a future HTTP dependency must perform current
  token/session resolution for reads as well.
- **Learner authorization exists:**
  `authorize_learner_action(db, principal, learner_id, action)` returns
  `LearnerAuthorization(actor_id, learner_id, action, access_path,
  basic_profile_fields, consent_evaluated=False)`. Global role alone is insufficient.
  Self requires the linked learner user. Guardian viewer/manager relationships
  permit guardian-summary reads; educator viewer/instructor assignments permit
  educational-summary reads, with active assignment semantics. Learning interaction
  is permitted to self and qualifying educator instructors, not guardian viewers.
  Approval of Component 4's exact disclosure/action matrix remains outstanding.
- **Consent evidence exists, consent evaluation does not:** Learners owns
  `ConsentNoticeVersion` and `ConsentRecord` models for guardian consent and learner
  assent. Their existence, and an authorization grant, do not imply permission to
  process a learner's sessions. No approved public evaluator is wired for
  `ConsentChecker(db: Session, learner_id: UUID, purpose_code: str) -> None` with
  purpose `learning_support`. Missing evaluator fails closed. Teammates must supply
  age/context rules, current notice policy, guardian authority checks, withdrawal
  and concurrent-revocation semantics, sanitized errors and retention decisions.
- **Recommendation settings are different from accessibility preferences:**
  Learners' public `read_preferences` exists but returns language, text scale,
  line spacing, theme and reduced motion. It does not supply Component 4's
  `LearnerReadingSupportSettings` or the authoritative `SupportPreferences`,
  manual lock, current difficulty/support context and consistent versioned read
  needed by the adaptation mapper. Do not map accessibility defaults to adaptation
  preferences. The latter settings read and orchestration remain Component 4 work,
  gated on the policy decisions in section 7.

### Reuse inventory and remaining activation work

| Existing boundary | Reuse / limitation |
| --- | --- |
| `ReadingSessionIngest`, canonical digest, ingestion service | Reuse directly after approval; do not duplicate formulas or idempotency storage. No upstream mapper exists yet. |
| History repository / historical mapping | Reuse learner-scoped bounded queries; do not return partial overflow results or query another module's tables. |
| Three private API adapters and service policies | Already implemented and unit tested; Component 4 router is empty (although shared composition includes that empty router). No feature HTTP endpoints are enabled. |
| Completed-evidence adaptation mapper and advisory rule engine | Pure and available; authoritative settings read, partition selection and authorized orchestration are not implemented. No automatic application. |
| Closed narrative contracts/evidence/validator | Available and inactive by default. Ollama/OpenAI developer transports rebuild only fixed synthetic fixtures; never reuse them for real learners. |
| Expo provider + presentation hook | Existing fixed role methods and stale-result suppression. Live provider rejects all 7/30/90-day requests; no network and no demo fallback. |
| Offline Qwen3 snapshot and native PDF | Preserve as explicit development-only learner synthetic features. January snapshot facts never mix with dashboard demo facts. Not a live-data provider or production export permission. |
| `packages/api-client` | README placeholder only. Generate approved role-separated contracts after route/OpenAPI approval; do not hand-code a competing client. |

Component 4 still owns: a reviewed mapper from the eventual producer contract;
authoritative support-settings retrieval and advisory recommendation orchestration;
approved inactive-to-active API wiring and security/error/no-store tests; generated
client consumption and real-data presentation mapping once those contracts exist.
Shared endpoint registration, secure mobile auth/learner selection, consent policy,
producer provenance and persistence/retention policy require teammate approval.
Future learner switching must change request identity/cancel old results; current
preview providers do not accept learner IDs and cannot stand in for that integration.

### Verification and recommended next coding step

STEP 170 adds no runtime adapter or endpoint. It extends the existing synthetic
in-memory ingestion flow through serialized input, role projection and factual report
construction while proving default narrative generation remains disabled. It also
checks that all three mobile live-provider methods fail for every 7/30/90-day period
without network access or a successful synthetic substitute. Existing security,
retry, missing-data, stale-result, report and PDF tests are retained.

**Next:** have Speech and Adaptive Reading owners publish and approve one synthetic
finalized-session example plus field definitions/provenance and retry/correction
policy. Add the smallest Component 4-owned translation contract test against that
actual DTO using `ReadingSessionIngest`; do not guess a producer adapter now. In
parallel, the Learners/Consent owner must deliver the public `learning_support`
evaluator and withdrawal/concurrency contract before any real-data route activation.
PostgreSQL-backed integration/concurrency tests remain unrun in this readiness step.

## 14. STEP 171 independent synthetic finalized-session integration tests

No additional simulator or production adapter was necessary. The existing
`tests/unit/test_learner_integrated_reading_flow.py` already has `_payload`, which
produces a validated, explicitly contextualized finalized `ReadingSessionIngest`,
and `_SyntheticComponent4Store`, an in-memory repository double. Both remain test-only.
They neither define the Speech DTO nor register routes, access PostgreSQL, select
real learners or add a synthetic fallback to any live provider. Authorization and
consent are explicit test doubles, not approved production integrations.

The existing tests continue to exercise ingestion, exact/conflicting retries,
completed/abandoned/interrupted sessions, all three projections, missingness,
completed-only advisory adaptation, reporting bounds, consent denial and factual
report evidence with the narrative provider disabled. STEP 171 additionally checks:

- Actual ingest-calculated accuracy `0.9600`, WPM `100.00` and hesitation rate
  `0.0200` for the original completed-session fixture, without copying formulas.
- Six varied completed sessions arriving in reverse or shuffled order produce the
  same three projections, recommendation and role-specific factual report requests
  as chronological arrival. First/latest accuracy remains `0.6300`/`0.7800` and
  hesitation rate `0.0700`/`0.0200`. Fingerprints remain distinct across roles.
- A completed session with zero active duration and unmeasured hesitation retains
  missing calculated metrics. Five valid measurements out of six are reported
  truthfully; missing core evidence prevents a change recommendation and the report
  preserves insufficient-evidence and missing-is-not-zero explanations.
- Invalid counts, duration bounds, naive/reversed times, session UUIDs, completion
  states and client-calculated scores fail at serialized input validation and leave
  previously ingested progress unchanged.
- Even an exact retry must pass current consent checks before idempotency lookup.
  Missing or withdrawn consent cannot return a previously ingested session.

The repository double sorts by observed time/identity and replaces persistence.
These tests therefore demonstrate orchestration/analytics behavior under that
contract, not actual SQL execution, row locking, race resolution, durability or
upstream compatibility. Existing repository and service tests remain authoritative
for their respective units. Disposable PostgreSQL validation still requires a
separately authorized step; no database-backed tests run here. Synthetic support
preferences and manual-lock inputs are provided only by tests, never inferred as
real settings. No model request is made and saved Ollama snapshots, PDF export and
mobile UI are unchanged.

Run the focused suite from `apps/backend`:

```powershell
uv run --frozen pytest tests/unit/test_learner_integrated_reading_flow.py tests/unit/test_learner_telemetry_contract_integration.py -q
```

Pending teammate mapping decisions remain those in section 13: authoritative word
alignment/count semantics, hesitation thresholds, clocks/active time, session/context
ownership, nullable measurement handling, finalization/retry/correction identity,
producer provenance and any versioned DTO envelope. No proposed mapping is treated
as the final Speech/Adaptive Reading interface. Consent and disclosure approvals
remain prerequisites for activation.

**Next independent Component 4 task:** extend the same test-only workflow with
multiple task/difficulty/support partitions and explicit synthetic manual-lock and
support-preference scenarios. Verify partition isolation from history through
recommendations and report evidence without guessing upstream DTOs or activating a
settings service. Authoritative settings retrieval remains a separate approved
implementation decision; all recommendations remain advisory and never auto-apply.

## 15. STEP 172 context isolation and manual support lock verification

Only the existing test fixture and integrated-flow tests were extended. `_payload`
now accepts existing approved task, difficulty and support values explicitly; no new
DTO, setting, lock type, simulator service or runtime behavior was introduced.

### Verified context isolation

The 12 new context cases vary one partition dimension at a time (task type, difficulty
tier or observed support mode), use either three or six primary completed sessions,
and exercise chronological/reversed arrival plus exact retries. Adding three poor
measurements in another context does not change the original context's projection,
recommendation inputs or advisory decision. Exact retries add no observations.

The three-session contexts do not borrow each other's observations to reach the
six-valid-observation requirement for longitudinal comparisons. A six-session context
keeps its sufficient evidence when unrelated incomplete measurements are added in a
separate context. Unmeasured hesitation in that separate context remains null, with
zero valid and three missing measurements. No scores or missing values are imputed.
The existing longitudinal calculations, projection builders and report evidence
builder are used unchanged. Report evidence retains its insufficient-evidence notes.

Learner, Guardian and Educator projections retain their disclosure allowlists:
Learner metrics omit valid/missing-count detail, Guardian omits internal comparison
window means, and Educator retains approved comparison detail. Identifiers and
experimental engagement remain excluded. These assertions supplement existing
cross-role/cross-learner denial tests; test principals/grants do not establish real
teammate authorization compatibility.

Context means exactly `(task_type, difficulty_tier, support_mode)` in the current
contracts. Document ID/content identity is not an analytics partition key. Per-book,
per-document, language, curriculum or new content-level partitions are unsupported
without approved contract/calculation changes. No such separation is claimed here.
Longitudinal evidence needs six valid observations, while the separately versioned
advisory mapper/engine has its own minimum-session and complete-core-metric rules.
A limited trend does not automatically imply the same adaptation outcome.

### Verified lock/override precedence

Twelve new integrated cases exercise three existing support modes, both values of
`manual_override_locked`, and either sufficient or limited/missing completed-session
evidence. History and the completed-evidence mapper provide the real adaptation input;
`SupportPreferences` and lock state are explicit synthetic test settings, not values
inferred from the session or consent grant.

The current engine's precedence is:

1. `baseline_fixed` always returns `maintain`, reason `baseline_fixed_mode`, even
   when the explicit lock is true. Its manual-override flag remains false because
   fixed-baseline preservation is the rule that matched first.
2. Otherwise an explicit manual lock or observed `manual_override` mode returns
   `maintain`, preserving difficulty and support mode with no support adjustments.
   Explicit lock uses `manual_override_locked`; unlocked manual-override mode uses
   `manual_override_active`. Both take precedence over insufficient evidence.
3. Only unlocked adaptive mode proceeds to insufficient-evidence handling or the
   evidence-based adaptive rules. The sufficient strong-reading fixture recommends
   increased difficulty; the incomplete fixture returns insufficient evidence.

All cases remain advisory with `safe_to_apply_automatically=False`. Input support
preferences and observed session support modes are unchanged; no settings write is
performed. This tests recommendation suppression and immutability, NOT database
locking, authorized lock ownership, concurrent updates or confirmed application.

Only a single existing global lock boolean is supported by this contract. Per-field
locks, lock expiry, actor/guardian/educator ownership, changing a lock on a device,
and persisted lock enforcement are not invented or implemented. An authoritative
versioned support-settings read and approved lock/withdrawal transaction semantics
remain blockers before a real recommendation service can be activated.

Run focused verification from `apps/backend`:

```powershell
uv run --frozen pytest tests/unit/test_learner_integrated_reading_flow.py tests/unit/test_learner_adaptation_mapping.py tests/unit/test_learner_adaptation.py tests/unit/test_learner_longitudinal.py -q
```

No PostgreSQL, producer, AI model, production endpoint or live mobile provider is
called. Repository/auth/consent test doubles remain test-only. Existing synthetic
Ollama report artifacts, PDF export and mobile UI are untouched.

**Next independent task:** extend the test-only integrated evidence path with
half-open reporting-window boundaries and equal-time session ordering, verifying
that excluded/overflowing evidence cannot yield a partial recommendation or factual
report. Reuse the existing historical bounds and ordering contracts; do not add a
production settings or producer adapter until its external contracts are approved.

## 16. STEP 173 reporting windows and equal-time ordering

Sixteen additional integrated test cases reuse the existing finalized-session helper,
repository double, ingestion service, analytics, adaptation mapper and report builder.
The fixture now accepts an aware start instant; the repository double optionally
accepts fixed stored-row UUIDs so tests do not confuse them with retry UUIDs.
No runtime bug was found and no Component 4 runtime code changed.

### Reporting boundaries verified

The existing interval is `[start_at_utc, end_at_utc)`, evaluated against
`session_start_time`. The twelve boundary cases combine forward/reverse/shuffled
arrival, UTC/UTC+05:30 representations and measured/missing hesitation variants:

- A session one microsecond before start is excluded, even if it ends inside.
- A session exactly at start is included.
- A session one microsecond before end is included, even if it ends after end.
- Sessions exactly at end and one microsecond after end are excluded.
- The six eligible sessions alone supply counts, first/latest values, comparison
  windows, recommendation means and all three role-specific factual reports.
- Adding extreme out-of-window measurements changes none of those outputs. Excluded
  rows do not consume the selected result limit. Exact retries in equivalent UTC
  representation return existing sessions rather than adding observations.
- Missing eligible hesitation remains missing; outside measurements cannot fill it.
  The mapper/engine returns insufficient evidence when required eligible metrics
  are incomplete. The role projections retain their approved disclosure boundaries.
- Historical queries/projections normalize aware intervals to UTC. Tests exercise
  UTC and fixed UTC+05:30 offsets, not every timezone or daylight-saving policy.
- Passing unwindowed history to completed-evidence selection fails closed. The
  result-size guard runs first; with a sufficient limit, the out-of-window guard
  rejects those same records. Neither truncation nor silent filtering is introduced.

A separate empty-window case contains only stored sessions outside the requested
period. All role projections report zero included sessions, no context and no
manufactured first/latest metrics. Factual evidence states zero sessions. The
completed-evidence mapper rejects a requested partition that does not exist; it does
not synthesize an adaptation input or an action. A future authorized recommendation
service still needs an approved unavailable/empty-result presentation contract.

### Equal-time ordering verified and limits

The SQL contract orders by `(session_start_time ASC, ReadingSession.id ASC)`.
Historical mapping uses that stored row UUID as the longitudinal session identifier;
analytics orders by `(UTC observed_at, canonical session-id string)`. Fixed-width
canonical UUID strings preserve the UUID order used in this contract.

Three arrival-order cases use six different sessions at one timestamp and fixed
stored UUIDs deliberately opposite to the client retry UUID order. They verify
stored-ID ordering, first/latest accuracy `0.8500`/`0.6000`, early/late means
`0.8000`/`0.6500`, distinct exact retries and six included observations. Reversing the
repository result independently of the double's normal sort preserves all three
projections, the advisory decision and the complete factual report requests.

This guarantee applies to the same persisted sessions/row IDs. It does not promise
identical ordering if a fresh database assigns different row UUIDs to new inserts,
or that `client_session_id` determines the tie order. Canonical UUID ordering is a
deterministic tie-breaker, not evidence of physical chronology between simultaneous
observations. The current algorithm accepts such ties; whether producers should
combine them, use more precise timestamps or reject simultaneous finalized sessions
remains an external policy/measurement-contract decision. No new policy is assumed.

Repository filtering/sorting is simulated in the integrated tests; actual SQL
predicates/order clauses also retain their existing repository unit coverage. No
PostgreSQL execution, concurrency, durability, real Auth/Consent or upstream producer
compatibility is claimed. No model requests were issued. Synthetic-only mobile
snapshots, PDF export, UI and inactive live providers are untouched.

Focused checks from `apps/backend`:

```powershell
uv run --frozen pytest tests/unit/test_learner_integrated_reading_flow.py tests/unit/test_learner_historical_retrieval.py tests/unit/test_learner_longitudinal.py tests/unit/test_learner_adaptation_mapping.py tests/unit/test_learner_report_generation.py -q
```

**Next independent task:** test mixed-version, duplicate-identity and malformed
historical evidence across the existing mapper/report boundaries, verifying fail-closed
or insufficient-evidence behavior rather than partial recommendations. Keep it
synthetic and test-only; upstream DTO/provenance, timestamp-resolution decisions,
authoritative settings/locks, consent evaluation and disclosure approvals remain
external activation gates.

## 17. STEP 174 historical evidence integrity

Sixty-two additional integrated cases reuse the existing six-session fixture, real
Component 4 ingestion/mapping/calculation/projection/report functions, and test-only
repository/auth/consent doubles. No runtime services, migrations or policies were
introduced. No silent corruption was found in the exercised existing contracts.

### Invalid batches and identities

- Forty-two malformed-history cases cover every fixed role path with impossible
  counts/durations, negative counters, NaN/infinite/non-integer/boolean values,
  missing required measurements/context fields, unsupported context/completion values
  and naive timestamps. The entire historical batch raises the sanitized
  `HistoricalDataIntegrityError`; it is not partially projected. Report construction
  is never reached. Completed-evidence selection also rejects it before a
  recommendation can be built.
- Nine stored-identity cases repeat the same row UUID with identical measurements,
  conflicting measurements or conflicting completion state. Longitudinal analytics
  rejects duplicate session identifiers and the completed-evidence mapper rejects
  duplicates across all completion states, rather than deduplicating selectively.
  No report or inflated session count is returned. Existing shuffled/reversed-history
  cases remain in the suite and verify deterministic outputs for valid identities.
- Four retry/correction cases repeat exact client deliveries three times, then try
  changing counts, completion state, task or timestamp under the same learner/client
  UUID. Exact retries add no sessions; changed payloads return `409 digest_conflict`.
  Existing projections and complete factual report requests remain unchanged.
- An abandoned session is excluded from completed recommendation evidence; explicitly
  passing it to `CompletedSessionEvidence.from_observations` is rejected. Changing
  its status to completed under the same client identity is a conflicting retry.
  Descriptive dashboards may still count recorded incomplete sessions: completed-only
  filtering is an adaptation contract, not a claim that every dashboard row completed.
- Corrupt cached calculated columns do not supply historical report measurements.
  The repository's minimal raw-record contract and existing mapping recalculate
  accuracy/WPM/hesitation; identical validated raw evidence yields the same report.
  This is not permission to keep corrupt persisted columns or a database repair policy.

Duplicate row IDs currently surface a `ValueError` from longitudinal analytics;
completed-evidence selection uses `AdaptationMappingError`. Other malformed raw
records use `HistoricalDataIntegrityError`. These all fail closed internally, but
future HTTP error normalization must not leak exception details. No HTTP endpoint
is active and no new error-mapping policy was invented in this step.

### Versions: supported contracts and explicit limitations

There is **no historical-record schema-version field** or producer-version envelope
in `HistoricalSessionRecord` / `ReadingSessionIngest`. The historical projection also
omits `client_session_id`. Do not invent a historical `schema_version` or pretend an
unsupported legacy producer payload has been checked. Legacy schemas, correction
migration, source/model provenance and event-envelope compatibility remain approval
and contract work.

The distinct version concepts in current code are:

| Existing concept | Verified semantics / limit |
| --- | --- |
| ORM `row_version` | Optimistic concurrency value, not a historical schema or formula version. Its database behavior was not executed here. |
| Canonical digest `v1` | Backend hashing-format identity for retry equality, not producer compatibility. |
| `longitudinal_calculation_version` | The typed report accepts `v0.1-early-late-3`; explicit unknown/empty values fail model validation before projection. Three cases exercise this boundary. |
| Core metric versions | Historical mapping recalculates using the current accuracy/WPM/hesitation functions. No stored per-core-metric version is consumed by this minimal history contract. |
| `engagement_formula_version` on observations | Metadata labels are bounded strings, not an approved-version allowlist. A consistent synthetic label is accepted; mixed labels block trend comparison and cause adaptation's engagement mean to be unavailable. Two cases verify this explicit existing rule. |
| Narrative `report-narrative-v1` | Existing closed narrative contract and exact factual validator remain unchanged; unrelated to persistence/schema migration. |

Mixed engagement does not invalidate complete core educational evidence. It cannot
silently contribute a combined engagement mean to adaptation, and experimental
engagement/version strings are excluded from all three role projections and factual
narrative requests. The role-specific report requests match those built from the
same baseline core measurements. A consistent unknown metadata label being accepted
is not evidence of algorithm compatibility; any future allowlist requires an approved
version/provenance contract, not assumptions in tests.

### What these tests cannot establish

- If a producer falsely labels an incomplete session as completed on its first
  delivery, the current record has no independent completion proof to contradict it.
  Producer provenance and finalization authority must be agreed. Never infer a
  completed state from numeric performance or fabricate a competing DTO.
- Historical records lack client retry IDs. If an external source supplies distinct
  row UUIDs for one logical event, history alone cannot prove they are duplicate
  client events. The existing ingestion idempotency key and database unique constraint
  are the intended boundary; fresh-ID correction/deduplication policy is not invented.
- Mocked persistence cannot establish SQL constraints, concurrent insert behavior,
  durability, live authorization/consent, or compatibility with unfinished producers.
  No PostgreSQL or model service was contacted. Mobile, saved snapshots, PDF export,
  inactive providers and production routes are unchanged.

Focused verification from `apps/backend`:

```powershell
uv run --frozen pytest tests/unit/test_learner_integrated_reading_flow.py tests/unit/test_learner_historical_retrieval.py tests/unit/test_learner_longitudinal.py tests/unit/test_learner_adaptation_mapping.py tests/unit/test_learner_report_generation.py -q
```

**Next independent task:** test sanitized propagation of malformed and duplicate
historical-evidence failures through the existing private reporting adapters, using
synthetic mocks only. Resolve the documented exception-category mapping before future
HTTP activation; do not register endpoints or relax validation. Source/schema
versions, completion provenance, logical corrections, authoritative settings and
consent/disclosure decisions remain external integration gates.

## 18. STEP 176 private authoritative support-settings read foundation

Implemented Component 4-owned `repository.get_support_settings` and
`support_settings._read_support_settings`. This supersedes earlier statements that
no settings read implementation exists, but does NOT satisfy production security,
endpoint or recommendation-orchestration activation gates.

The repository selects the existing `LearnerReadingSupportSettings` row by the exact
learner UUID with `one_or_none()`. It does not limit away duplicate rows, create a
row, invent defaults, lock rows, commit or own the transaction. `Session.no_autoflush`
prevents this query from flushing unrelated pending changes. Only the existing
Component 4 table is read. No schema or migration change was made.

The private service has three distinguishable outcomes:

| Outcome | Representation |
| --- | --- |
| Existing valid settings | Frozen, strict `SupportSettingsRead` projection |
| No stored row | `None`; no default object or inserted row |
| Invalid settings, wrong learner or duplicate rows | Sanitized `InvalidSupportSettings` exception |
| Repository/unexpected retrieval failure | Sanitized `SupportSettingsUnavailable` exception, never `None` |

The projection requires every existing configuration field plus positive
`row_version`: support mode, default difficulty, speech cues/rate, syllable and
phoneme assistance, visual pacing/rate, line focus, simplification, pause threshold
and the existing global manual lock. It excludes row/learner/editor UUIDs and
created/updated timestamps. It rejects extra fields, coercion, non-finite decimals,
invalid ranges, null required values and missing fields. Speech rate preserves
Decimal and the existing Numeric(3,2) precision contract. ORM objects are not accepted
directly as projection input; the service explicitly copies the approved field list.

Validation follows the existing model/migration constraints and support contracts.
It does not add a per-field lock, infer who owns a lock, reinterpret baseline/manual
precedence, turn observed session context into settings, or require a pacing rate
merely because visual pacing is enabled (the existing stored contract permits null).
The existing advisory engine retains its independent precedence rules unchanged.

### Security boundary and remaining blockers

This is an internal data-retrieval foundation, NOT an authorization/consent boundary.
It accepts no principal, action/access-path choice, consent assertion, UI payload or
preview preferences. No production module imports it and no route registers it.
A future approved caller must resolve the current authenticated principal, authorize
the exact learner/settings disclosure and evaluate active `learning_support` consent
before invoking it in the shared transaction. No callback stub or allow-all security
substitute has been introduced.

Outstanding decisions include settings-specific reader permissions/disclosure,
current consent/withdrawal evaluation, concurrency/version consistency with history,
missing-settings behavior at recommendation composition, server-owned partition
selection and separately authorized writes. A valid read projection is not permission
to apply an adaptation. No model, settings write, mobile integration or synthetic
fallback is connected by this step.

### Verification scope and next implementation

`test_learner_support_settings_read.py` uses synthetic ORM values and mocked SQLAlchemy
sessions only. It verifies valid/absent/invalid rows, exact modes/lock representation,
nullable pacing, strict bounds/types, immutable minimized output, wrong-learner
rejection, duplicate-row and repository-error sanitization, required fields,
repository learner filtering, autoflush suppression, no writes/default creation and
absence of production imports/routes. SQL is compiled for inspection without any
PostgreSQL connection. Database concurrency/durability remains unverified here.

**Next independent implementation:** add a pure mapping/composition boundary from
this validated settings projection to existing `SupportPreferences` and the advisory
mapper, taking already-authorized bounded evidence and an explicitly supplied
partition. Preserve `None` as an explicit missing-settings outcome rather than
creating defaults; reject inconsistent configured context rather than silently
choosing one. Do not select permissions, wire live routes, persist recommendations
or apply adjustments until the pending policies are approved.

## 19. STEP 177 pure settings-to-recommendation composition

Added private `recommendation_composition._map_support_preferences` and
`_compose_recommendation`. These reuse `SupportSettingsRead`, `SupportPreferences`,
verified `CompletedSessionEvidence`, the existing partition mapper and the existing
advisory engine. No thresholds/formulas, settings schema, persistence, routing,
mobile preferences or generated clients changed.

### Mapping and missing/error outcomes

Every preference field is copied explicitly: speech cues/rate, syllable/phoneme
assistance, visual pacing/rate, line focus, simplification and pause threshold. The
validated Decimal speech-rate multiplier is converted to the float required by the
existing preference contract; no new quantization or heuristic is applied. All other
values, including nullable pacing rate, retain their existing meaning. The original
settings projection, its row version and evidence remain unchanged. Row version is
not an engine input and this pure layer makes no concurrent-consistency claim.

The mapper revalidates even an existing `SupportSettingsRead` to reject invalid data
introduced via validation-bypassing `model_copy`/`model_construct`. It accepts no ORM
row, UI preview dictionary or `SupportPreferences` object as authoritative settings.
Serialization warnings are suppressed during revalidation so corrupted field values
cannot be printed by Pydantic serializers; invalid settings raise the same sanitized
`InvalidSupportSettings` exception as the reader.

`None` means absent settings and maps/composes to `None` without creating defaults,
assuming an unlocked state, constructing an adaptation input or calling the engine.
An invalid stored row and repository unavailability still raise distinct reader
exceptions before composition is reached. Composition does not catch those errors,
read a repository or reinterpret them as missing settings.

### Context and precedence

The caller supplies one explicit trusted `PartitionKey`. The selected difficulty and
observed support mode must match the supplied configured difficulty/mode. A mismatch
is rejected, rather than overwriting settings, substituting historical state or
selecting a different partition. This is a conservative composition precondition,
NOT an approved policy for choosing current/default versus historical context. A
production selector, including cases where settings changed after past sessions,
still requires policy approval. Task selection is explicit and other task partitions
do not contribute evidence to the selected recommendation.

Only verified completed-session evidence is accepted by the existing mapper.
Learner/Guardian/Educator dashboard projections cannot substitute for that evidence.
Empty/invalid evidence or a nonexistent partition remains an error even when settings
are locked; a lock does not authorize invalid evidence. With valid matched context,
engine precedence is unchanged:

1. Fixed baseline preserves its configuration, even with lock/limited evidence.
2. Manual override/global lock preserves mode/difficulty with no support adjustments.
3. Unlocked adaptive mode applies the existing insufficient-evidence or adaptive rules.

The same unchanged `AdaptationThresholds` instance is supplied to mapping and decision
calculation. Every successful recommendation remains advisory with automatic
application disabled. There are no settings writes, recommendation persistence or
confirmed-application records.

### Security and verification limits

This layer is private and unregistered, and has no production callers. It does not
resolve identities, authorize a role, evaluate consent or establish that the settings
and identity-free evidence belong to the same learner. A future approved caller must
bind those inputs to the same authorized learner/window, ensure a consistent settings
version/history view and select the approved context. No authorization/consent
substitute or client-selectable permission is introduced.

The new synthetic tests reuse existing settings and completed-observation fixtures.
They cover every preference, numeric bounds/null pacing, bypassed-invalid models,
missing rows, repository errors, fixed/manual/lock precedence, adequate/few/missing
measurements, context mismatch, task isolation, rejection of role projections as
completed evidence, unchanged inputs and absence of writes/routes/retrieval in pure
composition. The previous no-production-import test now permits only this named
private composition module to import the reader's validation error; composition has
its own tests prohibiting production importers and I/O dependencies.

No PostgreSQL or model requests were issued. Mobile UI, offline Ollama snapshot and
native PDF export are untouched. Production recommendation integration remains
inactive. Settings-reader permissions, consent/withdrawal, learner association,
consistent versioned reads, partition policy and approved endpoint/disclosure
contracts remain blockers.

**Next independent implementation:** add a minimized private presentation projection
for existing advisory decisions, clearly separating observed/configured state from
recommended state, evidence limitations and manual-control flags. Do not expose full
support settings, introduce role permissions, apply changes or register endpoints.

## 20. Private advisory recommendation presentation (STEP 178)

`recommendation_presentation.py` adds a pure, unregistered mapper for existing
validated decisions. It returns frozen, strict, extra-field-forbidden projections
with immutable nested values. Current state contains only configured difficulty,
support mode and global lock. Proposed changes contain only differing difficulty or
mode and existing engine support adjustments. Engine explanations and advisory
disclaimer retain their meaning; no new thresholds or claims are introduced.

Statuses distinguish `settings_unavailable`, `recommendation_unavailable` and
`available`. Missing settings have unknown control flags, never invented defaults.
Invalid settings remain a distinct reader validation error; repository errors must
propagate before mapping and must not be converted to absence. Invalid or inconsistent
decisions/context are rejected with a sanitized presentation error. Available decisions
must match existing composition for the supplied validated settings, completed evidence
and explicit partition. Empty or mismatched evidence cannot become a maintain decision.

Evidence state distinguishes unavailable, sufficient and insufficient. An
insufficient-evidence decision exposes its original explanations as limitations.
Fixed-baseline/manual/lock precedence remains unchanged: a baseline decision may win
while manual control is also present; the engine's blocked flag is kept separately.
Every output is advisory, disallows automatic application and records no applied
changes. No settings writes, network calls, repository access or routes are added.

Outputs omit learner identifiers, raw evidence, reason/rule IDs, row versions and full
settings. This identity-free projection grants no role permissions: a future approved
caller must bind settings, decision and evidence to one authorized learner/window,
enforce consent and role disclosures, ensure version consistency and select an approved
context. Role dashboard projections are not accepted as completed-session evidence.

Mobile compatibility was inspected only. Its simplified actions and `beginner` tier
label differ from the backend's precise actions and `early` tier; no silent translation
or live provider wiring was introduced. Existing mobile UI, Ollama snapshot and PDF
export are untouched. Production integration remains inactive.

Synthetic tests cover sufficient/insufficient evidence, all modes and global locks,
missing settings/decisions, invalid settings/context/altered decisions, support changes,
minimal disclosure, nested immutability and absence of production importers or I/O.
The composition import guard permits only this named private mapper as a new consumer.

**Next independent implementation:** create a private, explicit mobile-presentation
adapter using synthetic fixtures, documenting the action/tier translations and
unavailable states before any live wiring. Authorization, consent, learner association,
consistent settings/evidence versions, approved context selection and endpoint/role
contracts remain external approval blockers.

## 21. Backend recommendation offline mobile preview (STEP 179)

Private `recommendation_mobile.py` reuses the context-verified presentation mapper.
It explicitly maps early/intermediate/advanced to beginner/intermediate/advanced,
the three existing support modes to display labels, and all six engine actions to
separate labels (maintain, increase/reduce support, increase/decrease difficulty,
insufficient evidence). It does not collapse actions into the frontend demo rules.
Current summary, proposals, original explanations, limitations, evidence state and
fixed/manual/global-lock/blocked indicators are retained. Missing settings and missing
decisions remain distinct. Unknown or inconsistent decisions/context fail closed;
no settings are applied or persisted and the mapper has no production consumers.

The opt-in `recommendation_snapshot` module constructs only fixed synthetic completed
sessions, using the existing six-session adaptation fixture pattern and existing
settings contract. Unlike the identity-free report projection fixture, it must build
verified completed evidence with an explicit task/difficulty/support partition. It
reuses composition, presentation, labels and the existing deterministic engine, with
no database/network/model calls. The 30-day January fixture currently proposes trying
the advanced reading level from intermediate. No learner/session identifiers, raw
sessions or settings row versions are exported. The snapshot is validated before the
fixed Component 4 artifact is written; tests require exact engine/artifact agreement.

From apps/backend, explicitly regenerate with:

```powershell
uv run --frozen python -m app.modules.learner_modelling.recommendation_snapshot --development-synthetic-only
```

The development Learner Suggestions screen offers `View backend synthetic
recommendation`. Selection opens a separate offline layout labelled
`SYNTHETIC BACKEND RECOMMENDATION — ADVISORY ONLY`, using only the snapshot's period,
context and decision. Returning restores the unchanged ordinary demo. Invalid selected
artifacts show unavailable without substituting frontend recommendations. Production,
live mode and Guardian/Educator roles cannot select or read the fixture.

Mobile validation is intentionally a pinned bundled synthetic-fixture comparison,
not a general live DTO validator or an authorization boundary. It rejects changed
fields, explanations, context/period, extra keys and other roles; returned data is
detached from the pin. Regeneration must pass backend artifact agreement tests. No live
provider wiring, shared navigation, PDF or saved AI report changes are introduced.

On iPhone: start Expo Go in development, choose Learner, open Learning Suggestions,
and explicitly select the backend synthetic preview. Check the January period, current
support, proposed change, explanation and lock states, then return to demo suggestions.
Physical-device rendering has not been verified in this step.

Production still requires approved authentication, learner authorization and consent,
consistent settings/evidence versions and context selection, Speech/Adaptive Reading
measurement contracts, role disclosure policy and an approved API contract. Next
independent work: an explicitly selected synthetic preview of absent/locked/limited
recommendations, reusing this contract without changing production behavior.

## 22. Connected standalone synthetic file workflow (STEP 184)

`learner_modelling/connected_demo.py` is a private opt-in CLI, not an HTTP service.
It accepts only the version-2 synthetic developer-file envelope, validates all scalar
and relational telemetry through existing ReadingSessionIngest, rejects duplicates
and extra identity/role fields, and assigns one fixed synthetic learner internally.
It filters one explicit UTC half-open window, task, difficulty and observed support
mode, using completed sessions only for both longitudinal analytics and advisory
composition. Invalid excluded records still fail the entire import. No database,
Auth/Learners service or model invocation is performed.

The minimized learner artifact carries source digest, explicit period/context,
generation timestamp, included/excluded counts, approved learner metric projection,
advisory presentation or unavailable explanation, and synthetic-settings provenance.
Recommendations use the approved existing synthetic preferences configured for the
chosen context, not authoritative stored learner preferences. Missing/insufficient
evidence never becomes a fabricated recommendation or applied settings change.

Mobile exports saved validated sample records via existing native file/sharing
modules only on explicit developer action. The CLI writes a separate connected
artifact, fixture pin and synthetic source sidecar. Reproducibility tests rebuild
from that source; only the minimized artifact/pin are imported by UI code. Explicit
selection connects Learner Home/Progress/Suggestions/Profile to that one artifact.
Other roles cannot select it. Device session changes clear the selection, and no
live provider or network fallback is introduced. Settings/Feedback remain local
previews; the saved Qwen3 AI report/PDF remain independent and unchanged.

Instructions, example and limits are documented in mobile feature
`preview/DEVELOPER_SESSION_TEST.md`. This workflow requires computer-side import and
Expo reload. The fixture pin is not authentication or cryptographic provenance.
Production authorization/consent, upstream telemetry ownership, context/settings
version policy, approved APIs and live providers remain unresolved. Physical-device
file sharing and rendering have not been verified by this implementation.

## 23. Interactive connected sample replay and report preparation

The existing offline CLI now emits schema-v2 full and prefix artifacts, not another
service or a frontend rule engine. Prefixes reuse actual completed evidence,
longitudinal analytics, advisory composition and deterministic report evidence.
Chronological history omits session/learner IDs; experimental engagement appears
only in explicitly expanded synthetic developer diagnostics, without changing the
existing approved role projections. Generated source statements are deterministic
report preparation, not AI-generated content.

Mobile can replay prepared inputs one session at a time with immediate selection of
precomputed backend results. This is labelled as a prepared fixture and never claims
to calculate arbitrary form values. Home, Progress, Profile, Suggestions and report
preparation share the selected prefix's evidence, period, context and timestamp.
Custom inputs retain the explicit save/export/computer-import/reload workflow.
Raw saved views show inputs and backend-calculation-pending states instead of using
frontend formulas or unrelated fixture metrics. Empty/insufficient evidence remains
unavailable. No changes are automatically applied.

Exact local retries do not add/write duplicate observations; conflicts preserve prior
valid state. Reset supports zero-session replay or explicit developer-store clearing.
Settings/feedback remain independent local previews; parent/teacher screens remain
separate role-specific demos. The saved Qwen3 report/PDF require explicit independent
navigation, remain unchanged and are not derived from current sample sessions.

FR01/09: connected observational profile/history, not identity/profile maintenance.
FR02/08: existing temporary preference/support previews remain available, not
persisted authoritative support changes. FR03/04: validated sample capture/store and
idempotency, no upstream measurement capture. FR05: backend experimental diagnostic,
not validated engagement effectiveness. FR06/10: actual context-specific descriptive
analytics/history, not causal efficacy. FR07/11/13: backend explanatory advisory
recommendations, no adaptation application. FR12: same-source deterministic report
preparation plus separate saved synthetic AI/PDF. FR14: role-separated existing
parent/teacher demos, not authorized production reads. All production Auth/Consent,
upstream measurement, profile ownership, context/version and API approvals remain
external blockers. No PostgreSQL or live AI/network request was added.


## Optional Gemini synthetic report smoke test (STEP 198)

`gemini_report_smoke.py` is a private development harness, not an application
provider registration or production API. It binds requests to the existing fixed
synthetic learner projection; arbitrary caller evidence is rejected before HTTP.
No learner lookup, database, file export, mobile integration or provider fallback
is supported. Existing Ollama snapshot and native PDF remain unchanged.

Uses approved HTTPX development dependency and Gemini generateContent REST JSON
output (`responseMimeType` plus `responseJsonSchema`) with the unchanged closed
NarrativeDraft schema. Default model: gemini-2.5-flash; configurable reviewed
alternative: gemini-2.5-flash-lite. No tools or safety-setting overrides. Local
validation requires every approved evidence reference and statement exactly once;
JSON compliance alone is never treated as factual validation.

Only after explicit authorization for one external synthetic request, from
`apps/backend`, with GEMINI_API_KEY supplied securely in the process environment:

```powershell
$env:APP_ENV = "development"
$env:READBUDDY_SYNTHETIC_GEMINI_ENABLED = "1"
$env:GEMINI_REPORT_MODEL = "gemini-2.5-flash"
uv run --frozen python -m app.modules.learner_modelling.gemini_report_smoke --allow-gemini-request
```

Both enablement and CLI authorization are required; default is disabled. The key
is read only from GEMINI_API_KEY, sent in a header to the fixed Google HTTPS
endpoint, never printed or placed in URL parameters. Environment proxies and
redirects are disabled. One attempt, zero retries, 20-second total/HTTP timeout,
4,096 output-token ceiling, bounded streamed envelope and validated text limits.
CLI prints status and sanitized reason only; it does not save generated content.
Free-tier eligibility, quotas and provider data-use terms must be checked for the
selected project; this code does not guarantee free service. No live Gemini call
was made during implementation. Production Auth/Consent/authorization and real
learner report generation remain unconnected and unauthorized.

API contract reference: https://ai.google.dev/api/generate-content


## STEP 216: opt-in Gemini HTTP 400 classification

The existing --diagnostics flag additionally enables bounded HTTP 400 body
classification (16 KiB decoded bytes, existing 20-second request deadline, no
retries). Without diagnostics the error body is not read. Only Google AIP-193
error envelopes with code 400 / INVALID_ARGUMENT and google.rpc.BadRequest
fieldViolations are interpreted. Messages, descriptions and field names never
appear in output. No raw errors are logged or retained in diagnostics.

Categories: invalid_schema (explicit schema field violation),
unsupported_generation_parameter / unsupported_model_parameter (known parameter
field plus a narrow exact unsupported description), invalid_request (explicit
INVALID_ARGUMENT without more details), unknown (malformed, oversized, ambiguous,
conflicting or unrecognized details). Recognition rules are not claims about
which error detail texts Gemini actually returns. Message-only responses remain
unknown unless the consistent status envelope establishes generic invalid_request.
No keyword inference or arbitrary ErrorInfo reason mapping is performed.

References: https://google.aip.dev/193 and
https://github.com/googleapis/googleapis/blob/master/google/rpc/error_details.proto

After separate authorization, with the existing development gates and securely
supplied GEMINI_API_KEY, from apps/backend:

```powershell
$env:GEMINI_REPORT_MODEL = "gemini-3.1-flash-lite"
uv run --frozen python -m app.modules.learner_modelling.gemini_report_smoke --allow-gemini-request --diagnostics
```

No live call was made in STEP 216; HTTP 400 is not claimed fixed. Request schema,
factual validation, role boundaries, Ollama, snapshots and PDF remain unchanged.


## STEP 218: isolated Gemini request variants

The standard request and default model are unchanged. No field rejection is
confirmed from HTTP 400 / INVALID_ARGUMENT alone. Reviewed separately: v1beta
endpoint, gemini-3.1-flash-lite model, 4096 output-token cap (documented model
maximum 65536), generationConfig nesting, minimal thinking level, systemInstruction,
and non-recursive closed report schema. Unsupported schema keywords may be ignored;
this does not prove they caused the rejection. Current REST docs also demonstrate
responseFormat.text with mimeType APPLICATION_JSON and schema.

Explicit --request-variant choices (one request per invocation, never an automatic
sequence): standard; no-thinking (omit only optional thinkingConfig); response-format
(use documented responseFormat.text instead of legacy MIME/schema fields);
inline-schema (inline the fixed ReferencedStatement definition, preserving all
constraints, removing only the now-unused $defs/$ref). Nonstandard variants require
--diagnostics, the existing request authorization, all development/synthetic gates,
and model gemini-3.1-flash-lite. All retain the same synthetic evidence, instructions,
4096-token ceiling, response bounds, deadline and full local factual validator.
No free-form or partially validated response is accepted; no output file or mobile
snapshot is written. Success would demonstrate acceptance of that variant, not
prove a unique cause without comparison against the baseline.

Suggested next separately authorized experiment, from apps/backend with existing
environment gates and securely supplied GEMINI_API_KEY:

```powershell
$env:GEMINI_REPORT_MODEL = "gemini-3.1-flash-lite"
uv run --frozen python -m app.modules.learner_modelling.gemini_report_smoke --allow-gemini-request --diagnostics --request-variant no-thinking
```

No live request was performed during implementation. References:
https://ai.google.dev/api/generate-content
https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
https://ai.google.dev/gemini-api/docs/generate-content/thinking
https://ai.google.dev/gemini-api/docs/generate-content/structured-output


## STEP 222: independent Gemini text connectivity probe

`--connectivity-only` selects a separate status-only function. It sends only the
fixed harmless prompt "Reply with the single word Hello." and maxOutputTokens 64.
No schema, evidence, system instructions, thinking configuration, tools or caller
input are included. It never calls report builders or validators and cannot return
a ReportGenerationResult, narrative or snapshot. Returned text is discarded after
checking one completed model text response. No raw response is printed or saved.

Existing development/synthetic gates and --allow-gemini-request are mandatory.
Same fixed HTTPS endpoint, model allowlist, environment-only key, disabled proxies
and redirects, 20-second total/HTTP deadline and zero retries. Decoded response
limit is 16 KiB; returned text limit is 1024 characters. Existing --diagnostics
emits only sanitized status/category/phase/timing. A blocked, truncated, malformed
or empty response does not count as verified text generation. Probe cannot be
combined with report request variants.

After separate authorization, from apps/backend with existing development gates
and securely supplied GEMINI_API_KEY:

```powershell
$env:GEMINI_REPORT_MODEL = "gemini-3.1-flash-lite"
uv run --frozen python -m app.modules.learner_modelling.gemini_report_smoke --allow-gemini-request --connectivity-only --diagnostics
```

connectivity_verified means a bounded completed text response was received for this
probe only. It does not validate structured report compatibility. HTTP 401/403/404
can indicate access issues; 503 is a provider/service failure and alone cannot
establish schema incompatibility. No live call was made during implementation.
Official reference: https://ai.google.dev/api/generate-content


## STEP 236: Gemini transport-schema representation

Audit: NarrativeDraft has two closed object levels (report and statement), one
array, three required report fields and two required statement fields. The only
reference is non-recursive #/$defs/ReferencedStatement, with no sibling keywords.
Google documents definitions/references, nested objects, required fields,
additionalProperties, minItems/maxItems and string enums. The array bound is
1..1024. There are no numeric metrics or numeric range restrictions in the output
schema: validated measurements are already embedded in approved statement text.
There are no format keywords. pattern, minLength/maxLength and const are outside
the guide's listed subset; unsupported properties may be ignored, not necessarily
rejected. No documented numerical nesting/complexity limit is proven exceeded.
HTTP 503 is not evidence of schema incompatibility; basic HTTP 200 connectivity
does not establish report-schema acceptance.

New explicit --request-variant transport-schema uses a private schema generator:
inline the single definition; const becomes a single-value enum; omit transport
pattern and text length keywords. Preserve required fields, object closure, array
bounds and all field names. The response maps identically with no repair, coercion,
defaults or invented statements. Original NarrativeDraft, NarrativeRequest and
validate_narrative remain unchanged; local regex, length, fingerprint, role-bound
evidence references and exact statement validation remain mandatory twice.

The standard request and all existing variants remain unchanged. This alternative
still requires development/synthetic gates, explicit request authorization,
--diagnostics and model gemini-3.1-flash-lite. It does not enable production or
write any snapshot. No live call occurred and no HTTP rejection cause is confirmed.

Official references reviewed:
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
https://ai.google.dev/api/generate-content

Recommended next step: review this transport representation and mocked validation
coverage; only after separate authorization consider one transport-schema smoke
request. No additional live calls are required by STEP 236.


## STEP 246: standalone demonstration data lineage

DemoLearnerCard defines display-only Demo Learner, sample age 10, and DEMO-001
(the existing PDF's demo ID). Name/age are explicitly sample identity, never an
inference from UUIDs, reading performance, authentication or Learners records.
Demo identity is rendered only in demo presentations, not live provider output.

Connected Home/Profile/Progress/Suggestions/report preparation retain one selected
backend artifact/prefix, context and reporting period. Profile shows the same
metrics, history and demonstrated difficulty/support context; none establishes
reading age, diagnosis or authoritative stored settings. Temporary preference
summaries use the existing in-memory PreviewSession store and never become locks,
adaptation inputs or backend evidence. Support Settings now explains fixed,
adaptive and manual support without applying any of them. Existing feedback
answers, reset, role/live clearing and NOT SAVED semantics remain unchanged.
Progress exposes the existing experimental engagement value with an explicit
unvalidated-heuristic limitation; no attention or effectiveness claim is made.

Guardian/Educator retain their separate role-specific demo providers/fixtures;
the Learner connected artifact is not projected into those roles. Shared sample
identity does not imply shared session measurements across those independent demos.
Independent Qwen3 January snapshot/PDF, recommendation snapshot, and dashboard
fixtures remain separate. Gemini is not connected to mobile or production.

FR01-FR14 demonstration areas remain available. This does not complete real
profile maintenance, authoritative settings/feedback persistence, Speech session
capture, live analytics integration or evaluated personalization effectiveness.
Production remains blocked on approved Auth, learner-level role authorization,
Consent, Learners and finalized Speech/Adaptive Reading contracts.


## Current workspace completion audit - 21 October 2026

See [component-4-completion-audit.md](component-4-completion-audit.md) for the fresh
FR01-FR14 map, layer evidence, fixed defects, exact verification results and remaining
external contracts. The audit repaired PostgreSQL representation bounds, sanitized
unexpected ingestion consent failures, strengthened production/offline CLI import
isolation, and clarified Educator analytics PDF action labels. No production API or
live provider was activated. DATABASE_URL/TEST_DATABASE_URL are absent; a fresh bounded
local Qwen3 request timed out before response headers. This is not successful
production, database or AI verification.
