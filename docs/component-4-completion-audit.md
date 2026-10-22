# Component 4 current-workspace completion audit

Audit date: 21 October 2026. Branch: `feat/component-4-learner-analytics`.
Committed HEAD: `845bbd18c5076d7d42123e8d198eb9b9ac4a0bd2`.
All pre-existing uncommitted changes were preserved. This report describes the current
local implementation, not an older develop snapshot. No original proposal PDF/DOCX
was found in tracked/workspace file inventory; FR definitions below are those supplied
by the user. Demo functionality is not classified as production completion.

## Current verification

- `uv run --frozen pytest tests -q` in apps/backend: **1,258 passed, 299 skipped,
  zero failures**, one existing Starlette/httpx deprecation warning. The skipped
  database, integration, migration, concurrency and real-database authorization tests
  require an exclusive disposable PostgreSQL database; they are BLOCKED, not passes.
- Backend Ruff check, Ruff formatting check and mypy: PASS (86 app source files).
  Ruff covered app plus the three changed unit test files; formatting covered 89 files.
- `yarn test --silent`: **278 passed, 21 suites** (includes report, PDF, persistence,
  navigation and role-boundary tests). TypeScript and ESLint: PASS.
- `yarn doctor`: **21/21**. `git diff --check`: PASS.
- `uv run --frozen alembic heads`: exactly one repository head,
  `0006_learner_reading_sessions`. This does NOT establish the applied database revision.
- DatabaseSettings validation: DATABASE_URL missing. TEST_DATABASE_URL and reset opt-in
  are absent. No usable effective database URL could be confirmed. No database
  connection, data query, migration application, reset or creation was performed.
- Fresh real local Ollama attempt: API version 0.40.6, installed model qwen3:4b.
  Existing Learner synthetic harness, explicit opt-in, loopback only, one attempt,
  120-second cap. Result: unavailable/provider_timeout; last_stage waiting_for_headers;
  connection 1.605 ms, waiting 120014.543 ms, total 120020.802 ms; server counters empty.
  No generated content returned; factual validation of a fresh response is unverified.
  No external AI service was contacted and no saved snapshot was replaced.

## Confirmed defects fixed

1. The isolation assertion incorrectly treated reviewed offline exporter entry points
   as production services. It rejected educator_students and would also reject
   role_scenarios. The updated AST-based guard allows only those three reviewed
   offline entry points to share the synthetic workflow, forbids all other app modules
   from importing any of them, and prohibits direct database/network/auth/learner
   dependencies in each exporter. It catches plain imports, from-package imports,
   aliases and relative imports; regression cases verify these forms. No production
   module now imports a synthetic workflow, and no runtime route was added.
2. ReadingSessionIngest accepted integers larger than PostgreSQL INTEGER columns.
   Count/duration inputs now reject values above 2147483647. This is a storage
   representation limit, not a new educational threshold or formula.
3. Calculated WPM and hesitation ratios could exceed Numeric(7,2) and Numeric(6,4)
   before persistence. Ingestion now rejects these with sanitized 422
   measurement_out_of_range before insert/savepoint. It never clamps, substitutes
   missingness or changes formulas. Valid large values remain unchanged and retries
   still return the original authorized record before recalculation.
4. Unexpected ingestion consent-provider exceptions escaped unsanitized. Ingestion
   now reuses the same learning_support consent evaluator as dashboards: explicit
   SecurityError denials are preserved, unexpected failures become sanitized 503,
   and no repository read/write occurs on consent failure.
5. Educator PDF actions now explicitly say Download Student Analytics Report and
   Download Class Analytics Report. They cannot be mistaken for AI generation.

## Layer status and workflow tracing

| Area | Status | Evidence | Remaining issue |
|---|---|---|---|
| Database/migrations | PARTIAL / BLOCKED | shared app/db Base, session factory and registry; learner_modelling/models.py; migration 0006 | No effective DB URL or disposable DB; applied schema, constraints and transactions cannot be verified against PostgreSQL. |
| Backend APIs | PARTIAL / BLOCKED | learner_modelling/service.py, api_contracts.py, api_adapters.py; OpenAPI schema shows zero Component 4 paths; unit tests | learner_modelling/router.py is empty; approved consent callback and endpoint policy unavailable. |
| Learner | PARTIAL / demo | LearnerProfileScreen, PreviewSession, ConnectedLearnerJourney, ReadingResultsScenarios; demoPersistence tests | Shared Learners identity APIs exist, but Component 4 mobile does not call them; edited demo identity is not verified identity. |
| Guardian | PARTIAL / demo | GuardianSummaryScreen, role_scenarios.py, roleScenarioResults.ts | Separate permitted sample projection only; no production report API/mobile integration or Guardian AI/PDF workflow. |
| Educator | PARTIAL / demo | EducatorStudents, EducatorReadingOverview, educator_students.py | Fictional roster, role-projected sample histories, analytics PDFs; no real roster authorization or production class service. |
| AI reporting | BLOCKED / PARTIAL | report_contracts, report_evidence, report_narrative, Ollama/Gemini/OpenAI smoke tests | Fresh local request timed out. Existing validator permits exact catalogue statements only, not free-form analysis; only fixed Learner fixture accepted by provider adapters. |
| PDF exports | PARTIAL | localAiPdf.ts, educatorReports.ts, native sharing tests | Learner saved narrative and Educator factual analytics export exist; Guardian/class AI PDF absent; current iPhone pagination/share flow not physically verified. |
| Mobile | PARTIAL / demo | eight feature areas, feature-owned navigation, storage and provider tests | live provider always unavailable; no authenticated end-to-end data flow; physical layout/overlay checks pending. |
| Component integration | BLOCKED | ReadingSessionIngest, handoff producer contract, private reporting adapters | Approved producer DTO/provenance and consent evaluator missing; generated API client is a placeholder. |
| Security/permissions | PARTIAL | auth/learner action gates, fail-closed consent, role allowlists and unit tests | Real-database auth/concurrency tests blocked; demo role switch is not authentication. |

Actual current demo path:

Reading Results -> explicitly chosen validated scenario -> selected-scenario identifier
-> pinned Learner/Guardian/Educator role projections -> charts, observations, tips,
factual summary. Profile, settings and feedback use a separate versioned local demo
store. Custom raw inputs use honest laptop export/import; they do not run Python on
iPhone. Saved January AI snapshot stays separate from the chosen journey.

Intended production path:

Mobile authenticated client -> approved HTTP contract -> shared Principal + fixed
learner access policy -> approved learning_support consent callback -> Component 4
service/repository -> shared PostgreSQL -> minimized role projection -> mobile live
provider. It stops today before Component 4 HTTP/client integration; internal service
logic cannot be described as a working production mobile flow.

## FR01-FR14 mapping

All backend paths below are under apps/backend/app/modules/learner_modelling;
all mobile paths under apps/mobile/src/features/learnerModelling. Tests named
`test_learner_*` are under apps/backend/tests/unit unless noted.

| Requirement | Status | Implementation and regression evidence | What remains |
|---|---|---|---|
| FR01 individual profile | PARTIAL / demo | shared learners/models.py and service.py; mobile LearnerProfileScreen.tsx, DemoProfileEditor.tsx, PreviewSession.tsx; demoPersistence.test.tsx | Authorized identity/profile wiring, not a new Component 4 identity table. |
| FR02 support preferences | PARTIAL | models.py, schemas.py, support_settings.py, recommendation_composition.py; test_learner_support_settings_read; SupportSettingsScreen.tsx | Authoritative authorized write/service contract absent; mobile saved preferences are demo-only. |
| FR03 time/pauses/replays/completion | PARTIAL | ReadingSessionIngest, service.py, models.py; test_learner_reading_session_schemas/service; ReadingSessionTestScreen.tsx | Finalized producer contract, collection provenance and ingestion route. |
| FR04 performance/session storage | PARTIAL | repository.py, migration 0006, integration/test_learner_reading_session_ingestion.py | Real PostgreSQL validation blocked; no production HTTP ingestion. |
| FR05 engagement | PARTIAL / experimental | analytics.py, connected_demo.py; test_learner_analytics and integrated_reading_flow; ReadingProgress.tsx | Research heuristic is not scientifically validated; missing telemetry remains missing; no role disclosure expansion. |
| FR06 effectiveness/progress | PARTIAL | longitudinal.py, historical.py; test_learner_longitudinal and test_learner_historical_retrieval; readingProgress.test.tsx | Descriptive trends exist, not causal learning/personalization effectiveness. Needs connected real telemetry and study. |
| FR07 support levels | PARTIAL | adaptation.py, adaptation_mapping.py, recommendation_composition.py; adaptation/composition tests | Advisory rules exist; applying settings is intentionally inactive. |
| FR08 interface personalization | PARTIAL / demo | SupportSettingsScreen.tsx, PreviewSession.tsx; previewSession/demoPersistence tests; support_settings.py | Demo text preview works; no approved real reading-system settings writer. |
| FR09 profile updates after sessions | PARTIAL / demo | connected observations/history in ConnectedLearnerJourney.tsx; integrated_reading_flow tests | No authoritative profile-update transaction or producer-triggered update contract. |
| FR10 visualization | PARTIAL / demo | ReadingProgress.tsx, MetricChart.tsx, EducatorReadingOverview.tsx, dashboard_projections.py; mobile readingProgress and backend dashboard_projections tests | Production response mapping/generated client absent. |
| FR11 explain decisions | PARTIAL | recommendation_presentation.py, recommendation_mobile.py; recommendation tests; ConnectedLearnerJourney.tsx, LearnerSuggestionsScreen.tsx | Explanations work from validated prepared evidence; no production wiring. |
| FR12 AI progress reporting | PARTIAL / BLOCKED | report_contracts/evidence/narrative, ollama_report_smoke, local_report_snapshot; report/transport/PDF tests | Current real call timed out; no newly written analysis verifier, Guardian/Educator provider or class AI contract. |
| FR13 recommendations | PARTIAL | adaptation.py, recommendation_composition/presentation/mobile.py; LearnerSuggestionsScreen, recommendation tests | Advisory output only; no automatic application or production read endpoint. |
| FR14 parents/teachers | PARTIAL / demo | dashboard_projections.py, role_scenarios.py, educator_students.py; GuardianSummaryScreen/EducatorStudents; roleScenarioResults/educatorReports tests | Real authorized roster, consent, production endpoints and multi-role AI reports remain blocked. |

The original proposal wording for FR05/06 does not authorize clinical diagnosis or
validated causal conclusions. Fixed-baseline/manual/adaptive precedence has pure tests,
but comparative personalization efficacy, usability, transparency and acceptance
require a documented study protocol, consent, instruments and actual evaluation;
those are not established by synthetic tests or the role switcher.

## External contracts / owners

- Speech/reading measurement owner: finalized event DTO mapping to ReadingSessionIngest,
  immutable client identity, exact retries, completion semantics, units, missingness,
  version/provenance and delivery/ordering policy. No replacement Speech algorithm.
- Content/Adaptive Reading owners: approved task/difficulty/content identifiers and
  observed support exposure; applied support-setting interface and acknowledgement.
  Current document_id is an optional UUID context reference, not an invented new FK
  into another component's tables.
- Learners/Auth/Consent owner: real roster grants, fixed action/access paths, public
  learning_support consent/assent evaluator and withdrawal race semantics. Component 4
  must not query consent tables itself or treat a client role as authority.
- Shared API/client owners: approved route/response/error schemas and generated client.
  Current private adapters must remain unregistered until these policies exist.
- Research owner: supported engagement interpretation and evaluation protocol.

## Changes in this audit

- apps/backend/app/modules/learner_modelling/schemas.py: existing storage integer bounds.
- apps/backend/app/modules/learner_modelling/service.py: bounded persisted metrics and
  shared sanitized consent failure handling; no writes/API activation added.
- apps/backend/tests/unit/test_learner_connected_demo.py: import-graph boundary guard,
  reviewed offline-tool classification, no production import or network/DB exemptions.
- apps/backend/tests/unit/test_learner_reading_session_service.py: overflow/failure-path
  regressions and valid-large-value preservation.
- apps/backend/tests/unit/test_learner_reading_session_schemas.py: nine integer bounds.
- apps/mobile/src/features/learnerModelling/components/EducatorReportButton.tsx:
  unambiguous deterministic analytics action labels.
- apps/mobile/src/features/learnerModelling/__tests__/educatorReports.test.tsx:
  matching UI and native export expectations.
- docs/component-4-completion-audit.md: this evidence and requirements map.
- docs/component-4-integration-handoff.md: link to updated verified findings.

No migration, dependency, teammate module, production router, certificate, firewall,
external provider setting, AI snapshot or existing PDF renderer was changed. No stage,
commit, push, merge, rebase, reset or discard was performed.

## Prioritized remaining work

1. Configure a uniquely named local disposable PostgreSQL database ending in _test,
   inspect its effective credential-redacted target, then explicitly permit reset of
   that exclusive target only. Run the 299 blocked tests and migration/schema drift
   checks there. Never point them at the development application database.
2. Resolve local structured-generation latency using bounded content-free diagnostics;
   preserve factual validation. Introduce separately reviewed offline per-role report
   adapters and immutable display/export snapshots only after validated success.
   Newly AI-written prose and whole-class synthesis need evidence/verification contracts.
3. Obtain production consent + producer/relationship contracts; then register only the
   approved Component 4 routes, generate clients, and implement authenticated mobile
   providers with no synthetic fallback. This is dependency-driven, not a cosmetic fix.
4. Obtain applied-settings/profile update ownership contracts; implement private
   authorized persistence services and conflict/version tests before UI activation.
5. Run physical iPhone/Android tests: apply scenarios, restart persistence, switch roles,
   inspect all three fictional student histories, export selected student/class PDFs,
   check small-screen/large-text layout and overlay clearance, and inspect Alex A4
   pagination. Verify saved Learner AI source statements remain identical in its PDF.

No defensible production completion percentage can be assigned: essential consent,
producer and API contracts and real database/device verification remain outstanding.
Passing isolated algorithms and sample screens is not end-to-end production completion.
