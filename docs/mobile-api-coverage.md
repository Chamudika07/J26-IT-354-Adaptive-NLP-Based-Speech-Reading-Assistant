# Component 1 mobile API coverage

Audit: 2026-11-11. Source app factory and live `http://127.0.0.1:8000/openapi.json` are identical: **37 operations**. Snapshot: `packages/api-client/openapi.json`. Routers, service authorization and existing API tests inspected once. All listed operations have implemented services; verification below is separate from implementation.

Scope: all 37 registered operational public Component 1 operations have mobile actions. PASS HTTP below means verified against the disposable FastAPI/PostgreSQL fixture, not complete native-device acceptance. Paths below are relative to `/api/v1`; `L` = `/learners/{learner_id}`, `M` = `L/reading-materials`, `R` = `M/{material_id}/revisions`, `P` = `M/pdf-sources`.

Permissions: `auth` = active account/session; `admin` = administrator; `related` = matching current learner/guardian/educator relationship; `instructor` = active educator instructor grant. Administrator alone never grants learner content access. Target denials use 404, global role denials 403.

| Method | Path | Request → success response | Permission | Mobile | Verification |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | — → 200 HealthResponse | public | Connection status | PASS HTTP |
| GET | `/health/ready` | — → 200 HealthResponse | public | Connection status | PASS HTTP |
| POST | `/auth/users` | AccountCreate → 201 AccountCreated | admin | Admin → Create educator | PASS HTTP |
| POST | `/auth/login` | LoginRequest → 200 TokenResponse | credential | Sign in | PASS HTTP |
| POST | `/auth/refresh` | RefreshRequest → 200 TokenResponse | credential | Automatic rotation / session restoration | PASS HTTP |
| POST | `/auth/logout` | RefreshRequest → 204  | credential | Sign out | PASS HTTP |
| GET | `/auth/me` | — → 200 MeResponse | auth | Home → current account | PASS HTTP |
| POST | `/learners` | LearnerCreate → 201 LearnerCreated | admin | Admin → Create synthetic learner | PASS HTTP |
| GET | `/learners` | — → 200 LearnerListResponse | learner / guardian / educator | Home → authorized learners | PASS HTTP |
| POST | `L/educator-grants` | EducatorGrantCreate → 201 EducatorGrantRead | admin | Admin → Assign educator | PASS HTTP |
| POST | `L/educator-grants/{grant_id}/revoke` | — → 200 EducatorGrantRead | admin | Admin → Revoke access | PASS HTTP |
| GET | `L` | — → 200 LearnerDetailSelfGuardian / LearnerDetailEducator | related | Learner → Profile | PASS HTTP |
| GET | `L/preferences` | — → 200 LearnerPreferenceResponse | self / guardian | Profile → Preferences | PASS HTTP |
| PATCH | `L/preferences` | LearnerPreferenceUpdate → 200 LearnerPreferenceResponse | self / guardian manager | Preferences → Save | PASS HTTP |
| GET | `/assessment-materials` | — → 200 AssessmentMaterialPage | instructor (at least one learner) | Assessments → Available materials | PASS HTTP |
| POST | `L/reading-assessments` | AssessmentStartRequest → 201 AssessmentStartResponse | instructor | Assessments → Start | PASS HTTP |
| GET | `L/reading-assessments` | — → 200 AssessmentHistoryPage | related | Assessments → History | PASS HTTP |
| GET | `L/reading-assessments/{assessment_id}` | — → 200 AssessmentStartResponse / AssessmentSessionResponse | related | Assessment detail | PASS HTTP |
| POST | `L/reading-assessments/{assessment_id}/complete` | AssessmentCompletionRequest → 200 AssessmentSessionResponse | instructor + administering actor | Assessment → Complete | PASS HTTP |
| POST | `L/reading-assessments/{assessment_id}/abandon` | AssessmentAbandonRequest → 200 AssessmentSessionResponse | instructor + administering actor | Assessment → Abandon | PASS HTTP |
| POST | `M/pdf` | object → 201 UploadResult | instructor | PDF sources → Upload & extract | PASS HTTP |
| GET | `P` | — → 200 Page_SourceSummary_ | related | PDF source list | PASS HTTP |
| GET | `P/{source_id}` | — → 200 SourceSummary | related | PDF detail | PASS HTTP |
| POST | `P/{source_id}/extraction-runs` | ExtractRequest → 201 app__modules__reading_materials__pdf__schemas__RunDetail | instructor | PDF detail → Run / retry extraction | PASS HTTP |
| GET | `P/{source_id}/extraction-runs` | — → 200 app__modules__reading_materials__schemas__Page_RunSummary___1 | related | PDF detail → Extraction history | PASS HTTP |
| GET | `P/{source_id}/extraction-runs/{run_id}` | — → 200 app__modules__reading_materials__pdf__schemas__RunDetail | related | PDF detail → View attempt/evidence | PASS HTTP |
| POST | `P/{source_id}/archive` | ArchiveRequest → 200 SourceSummary | instructor | PDF detail → Archive | PASS HTTP |
| POST | `M` | MaterialCreate → 201 MaterialSummary | instructor | Learner → Create text | PASS HTTP |
| GET | `M` | — → 200 Page_MaterialSummary_ | related | Learner → Materials | PASS HTTP |
| GET | `M/{material_id}` | — → 200 MaterialSummary | related | Material results / manage | PASS HTTP |
| POST | `R` | RevisionCreate → 201 MaterialSummary | instructor | Manage material → New revision | PASS HTTP |
| GET | `R` | — → 200 Page_RevisionSummary_ | related | Manage material → Revision list | PASS HTTP |
| GET | `R/{revision_id}` | — → 200 RevisionDetail | related | Manage material → Original text | PASS HTTP |
| POST | `R/{revision_id}/processing-runs` | EmptyRequest → 201 / cached 200 app__modules__reading_materials__schemas__RunDetail | instructor | Material → Process revision | PASS HTTP |
| GET | `R/{revision_id}/processing-runs` | — → 200 app__modules__reading_materials__schemas__Page_RunSummary___2 | related | Material → Processing history | PASS HTTP |
| GET | `R/{revision_id}/processing-runs/{run_id}` | — → 200 app__modules__reading_materials__schemas__RunDetail | related | Material → Result | PASS HTTP |
| POST | `M/{material_id}/archive` | ArchiveRequest → 200 MaterialSummary | instructor | Manage material → Archive | PASS HTTP |

## Missing and internal-only capabilities

- OCR review/acceptance services and tables exist under `reading_materials/ocr`; **zero public OCR routes**, no enabled OCR engine. `ocr_required` is an extraction outcome, not completed OCR.
- No public registration, administrator creation, account list/edit, learner grant list, guardian provisioning, consent API, assessment material creation, material deletion or PDF binary download. Use the documented administrator bootstrap and reviewed internal material provisioning.
- `documents`, `simplification`, `speech`, `learner_modelling`, `numeracy` routers are empty placeholders. No mobile screens or new endpoints added for them.
- Learner list exposes only ID/name; it does not expose instructor capability. Mobile may show creation to educators but must handle viewer/expired grants denied by the server.
- PDF requires configured private storage. Compose currently binds API to 127.0.0.1; physical devices cannot reach that binding directly. PostgreSQL stays loopback-only.

## Current completion verification — 2026-11-11

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Live contract | PASS | GET /openapi.json 200; exact equality with generated snapshot, 37 operations; no schema changes |
| Persistent API health | PASS | GET /health 200; saved development API configuration is http://127.0.0.1:8000/api/v1; final native runtime reconnection remains unverified |
| Generated client → real FastAPI HTTP | PASS | 7 scenarios, zero skipped; every listed operation exercised against guarded disposable API on 18000 / PostgreSQL on 55432 |
| Mobile form/session/error regressions | PASS | 17 tests; concurrent rotation, restoration, invalid refresh, logout races, safe write retry, network uncertainty, SecureStore failure, validation and errors |
| Strict TypeScript | PASS | npm run typecheck |
| Backend regression | PASS | 557 tests, zero skipped: unit, health, onboarding, authentication, learners, assessments, materials, PDF public APIs; separate fresh disposable PostgreSQL 17 on 55433 |
| Backend quality | PASS | Ruff lint and formatting (163 files); strict mypy (102 source files) |
| iOS + Android bundle export | PASS | Both production Hermes bundles exported; not signed builds or device acceptance |
| New screens on native iOS | BLOCKED | Simulator rendered login and rejected a truncated automation-entered synthetic handle correctly. Window then became unavailable (cgWindowNotFound); dashboard, forms and native PDF picker acceptance remain unverified |
| Android / physical device / accessibility acceptance | SKIPPED | No device interaction; screen reader, large text and PDF picker/upload need device checks |
| Persistent server PDF readiness | BLOCKED | Private PDF storage is not configured in existing Compose environment. Disposable private storage workflow passes; no persistent configuration or data changed |
| Public OCR | BLOCKED / absent | No registered OCR routes or enabled engine; ocr_required is displayed as an outcome, never as successful OCR |
| Full backend suite including destructive migration fixtures | SKIPPED | Selected broader regression above avoids database-reset tests; no databases or existing volumes reset |

Real HTTP results: reads/login/refresh **200**; account/learner/grant/material/revision/
assessment creation **201**; first PDF upload **201**; cached operations **200**;
logout **204**; rejected credentials or revoked refresh **401**; educator attempted
admin action **403**; unrelated/revoked learner access and educator preferences
**404**; stale row versions and changed PDF retry metadata **409**; invalid text **422**.
Tests assert actual response bodies, including 10 correct words/minute for synthetic
observations and extracted PDF page evidence. No mobile-generated scores or fake data.

`MOBILE_HTTP_TEST=1 npm run test:mobile:live` runs sequentially to respect the existing
password-hash concurrency limiter. Running without the flag deliberately reports
SKIPPED. Fixture accounts and the original assessment passage exist only in disposable
storage. No production account passwords, roles or grants were changed.

## Contract and implementation notes

- Generated request/response schemas remain in `packages/api-client/src/schema.ts`.
  All 37 operations have existing services; none were invented. No production backend
  code or database schema was changed for this completion batch.
- Administrator home links to four dashboard actions. Administrator status never
  grants learner reading access. New IDs appear as selectable receipts, with manual
  ID entry for existing assignments because no account/grant directory API exists.
  Receipts are held only while the dashboard is mounted; passwords clear on success.
- Preferences enforce the existing self/guardian contract; educators receive 404.
  Blank preference values inherit defaults. Updates send row_version and surface
  conflicts. Assessment completion/abandonment is limited to its administering
  instructor; empty catalogs remain honest empty states.
- Assessment forms submit observations, not calculated results. New revisions
  retain the selected version and original text; archived material leaves active lists.
- Only refresh credentials persist in native SecureStore, namespaced by API URL.
  Startup rotates them through /auth/refresh. Concurrent 401s share one rotation;
  each request replays at most once after an explicit 401. Authorization runs before
  mutations on the backend. Network errors, timeouts, 403 and validation failures
  never automatically replay writes. Revoked refresh clears session and query cache.
- PDF multipart fields: title, language_tag=en, upload_request_id UUID, file. Picker
  copies to private cache, removed on completion/clear/unmount. Retries keep the same
  request ID, title and file. Extraction retries use the linked material's row_version;
  source archive uses the source row_version. Outcomes/evidence are rendered as returned.
  PDF POST timeout is 60 seconds to accommodate server extraction (up to 30 seconds).
- Lists preserve opaque cursors and load more. Permission errors hide stale content.
  Error text is sanitized; credentials, learner content and tokens are not logged.
- Current persistent API binding is loopback. iOS Simulator uses 127.0.0.1:8000;
  Android emulator uses 10.0.2.2:8000. Physical devices require the opt-in API-only LAN
  override in apps/mobile/README.md. Production requires HTTPS.

Next acceptance task: reopen iOS Simulator on the normal Metro session (8082), sign
in privately, open Administrator Dashboard, then exercise the new screens with a
synthetic educator/learner. Native PDF picker testing requires configured private
server storage or the isolated fixture. Android and assistive-technology checks remain.

## Earlier verification (historical, not repeated for this batch)

The initial vertical slice passed 391 focused and 1,260 broader backend tests, plus
native iOS educator login → authorized learner → create/process text → real results
and logout. Those results do not verify the newly added screens. The earlier dependency
audit reported five moderate Expo tooling advisories and no high/critical advisories;
no forced SDK downgrade was applied and the audit was not rerun for this batch.

## Login configuration fix — 2026-11-11

- Reproduced the reported login failure in iOS: the existing screen's API client
  still targeted the stopped disposable API on port 18000, while the current
  environment and freshly constructed client targeted port 8000.
- The runtime was created in a one-time React state initializer. Fast Refresh
  could retain it after the configured API URL changed. Providers now validates
  the URL on render and keys the session provider by that URL, replacing its
  client, session state and query cache together. Unmount cancels and clears queries.
- Login errors now distinguish rejected credentials, invalid input, throttling,
  server failures and connection guidance without reading-material write warnings
  or arbitrary exception content. Temporary diagnostic logging was removed.
- PASS: 11 focused mobile tests (including three login-error regressions), strict
  TypeScript, native sign-in/current administrator screen after reload. Backend
  logic, passwords, role grants and database volumes were not changed.
- Administrator-only learner denial is expected authorization behavior. The
  existing synthetic educator's expired instructor grant remains a separate
  onboarding task; this fix does not widen access.
