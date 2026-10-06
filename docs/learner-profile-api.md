# Learner Profile & Preferences API

Four endpoints extend the existing modular monolith. This sprint changes no tables,
indexes, dependencies, or migrations. Alembic remains at `0005_auth_sessions`.
No profile editing, learner creation, relationship management, consent execution,
account administration, or educational processing is added.

## Endpoints and public schemas

All endpoints require the current authenticated principal and return `Cache-Control:
no-store`. No client-supplied role or relationship data is accepted as authority.

| Endpoint | Response schema |
| --- | --- |
| GET /api/v1/learners | LearnerListResponse containing LearnerListItem |
| GET /api/v1/learners/{learner_id} | LearnerDetailSelfGuardian or LearnerDetailEducator |
| GET /api/v1/learners/{learner_id}/preferences | LearnerPreferenceResponse |
| PATCH /api/v1/learners/{learner_id}/preferences | LearnerPreferenceResponse; input LearnerPreferenceUpdate |

List items expose only `id` and `display_name`. Self/guardian detail exposes those
fields plus nullable `age_band` and `grade_level`. Educator detail omits age/grade
entirely. A complete self or guardian path takes precedence over an educator path.
The API never combines one role with a different relationship type to widen access.

Preferences expose `learner_id`, `row_version`, and the five preference values below.
Profile versions, timestamps, login linkage, creator/editor identity, preference-row
UUIDs, relationship evidence, account/session data, and consent records are excluded.
Public models are separate from existing storage-oriented read schemas.

## Authorization

Every access path requires its corresponding active role. Auth reads current account,
session, and role state on each request; no cross-request authorization cache is used.

| Actor/path | List and detail | Preference GET | Preference PATCH |
| --- | --- | --- | --- |
| Learner | Own linked, non-archived profile | Allow | Allow |
| Guardian viewer | Unrevoked linked learners | Allow | Deny |
| Guardian manager | Unrevoked linked learners | Allow | Allow |
| Educator viewer/instructor | Unrevoked links with expires_at > database time | Deny | Deny |
| Administrator alone | Deny | Deny | Deny |

Creation provenance does not grant access. A login-less learner is never implicitly
self; valid guardian/educator access still works. An administrator with an independent
active guardian role AND valid guardian grant uses that ordinary path only.
Archived learners and revoked/expired relationships never grant normal access.

Profile fields, including display_name, age_band, grade_level, learner_user_id,
created_by_user_id, and archived_at, cannot be changed by these endpoints.
Consent evidence neither grants access nor is required for these preference APIs.
Research/audio consent evaluation remains a separate future processing gate.

## Pagination

`limit` defaults to 25 and is bounded to 1–100. `cursor` is an optional UUID, meaning
strictly after that learner ID in PostgreSQL UUID order. There is no total count.

The repository unions eligible self/guardian/educator learner IDs, deduplicates them,
joins non-archived profiles, applies the cursor, orders by UUID, and fetches limit+1.
Authorization and deduplication occur before pagination. The guardian and educator
queries share the same predicates used by individual authorization checks.

`next_cursor` is the last returned ID only when another eligible row exists; otherwise
it is null. A cursor is a position, never a grant. It need not reference an existing
learner, so forged cursors do not disclose existence or widen access. Eligibility is
recomputed on every page request; pages are not a frozen snapshot across revocations.

## Preference validation and PATCH semantics

| Field | Accepted value |
| --- | --- |
| preferred_language_tag | Trimmed, nonblank string, at most 35 characters |
| text_scale | Finite decimal, 0.75–3.00, at most two decimal places |
| line_spacing | Finite decimal, 1.00–3.00, at most two decimal places |
| theme | system, light, dark, high_contrast |
| reduce_motion | Strict JSON boolean |

Each field also accepts null to reset its override. Omitted fields remain unchanged.
Decimal numbers and decimal strings are accepted, with no silent rounding; decimal
responses serialize as strings. Booleans are not decimal inputs and strings/numbers
are not booleans. The language tag is bounded text, not a promise of language support.

PATCH requires a strict integer row_version in 0–2147483647 and at least one explicitly
supplied preference field. Unknown fields are forbidden. Only the explicit preference
allowlist reaches persistence; target identity comes from the URL and editor identity
comes from the protected principal. No arbitrary profile update is possible.

```json
{
  "row_version": 3,
  "text_scale": "1.25",
  "theme": null,
  "reduce_motion": true
}
```

An authorized GET with no preferences returns row_version 0 and all values null,
without inserting a row. This is an API sentinel: persisted database versions are
positive. Null values are inherited overrides, not calculated device defaults.

The first version-0 PATCH creates version 1. Each successful subsequent PATCH advances
exactly once, even when the supplied values equal the existing values. Resetting to
null never deletes/recreates the row. Stale versions fail with 409; clients must GET
and reconcile changes instead of automatically retrying with an updated version.

## Transaction and module boundaries

Auth provides two explicit read-only contracts:

- `protect_principal_for_write` locks and revalidates account, session, active role
  definitions, and role assignments. It returns a fresh immutable principal.
- `assert_protected_session_live` rechecks token/session deadlines after domain lock
  waits, immediately before mutation. Locks cannot prevent time from passing.

Learners never imports auth ORM models or writes auth tables. Auth imports no learners
models and writes no learner rows. These contracts use the shared request session;
they acquire locks but never commit. The learners service owns commit/rollback.

Write lock order is user -> session -> role definitions/assignments (stable ID order)
-> learner -> supporting guardian relationship -> preferences. Auth role/grant locks
use SHARE mode; learner and preference rows are locked for update. Future lifecycle
writers must follow the same order when locking multiple kinds of rows. Do not perform
network calls or processing while these short database transactions hold locks.

After the auth locks, the learner row is locked and authorization reevaluated; any
supporting guardian relationship is protected through commit. The parent learner lock
serializes first creation and blocks archive/link changes. A current preferences row
is then locked and its version compared with the client version. The final deadline
check runs after lock acquisition, before any version-conflict disclosure or write.

Writes use ordinary versioned ORM flushes, with server-derived editor identity and
UTC time. An explicitly dirty update timestamp ensures accepted no-ops still perform
one version-checked UPDATE. No bulk update, manual client version assignment, or stale
write retry is used. The result is returned only after commit succeeds.

StaleDataError and the specific first-create unique-constraint conflict are translated
to 409 AFTER rollback. Other database failures retain the sanitized 503 contract.
Authorization precedes conflict disclosure. Invalid or revoked access cannot retrieve
current preference values through errors. Partial writes roll back on failure.

If revocation/archive wins the relevant lock, the write rechecks and fails. If a write
already holds its authorization locks, revocation waits for that short transaction;
subsequent requests see the revocation. Reads are authorized per request and do not
cancel responses already authorized before a concurrent state change.

## Errors

All use the existing `{ "error": { "code": "...", "message": "..." } }` envelope.

| Condition | Status/code |
| --- | --- |
| Missing/invalid principal or unusable account/session | 401 authentication_required |
| Collection without active learner/guardian/educator role | 403 forbidden |
| Missing, archived, unrelated, revoked, expired, or insufficient target access | 404 not_found |
| Stale preferences or concurrent first creation | 409 version_conflict |
| Invalid query/path/body | 422 validation_error |
| Database failure | 503 service_unavailable |

Conflict message: `Preferences changed. Reload and try again.` No current values or
relationship details are included. An eligible collection with no matches returns an
empty 200 response; administrator-only collection access returns 403. Target-specific
administrator denial remains 404. Validation errors never echo private input.

## Verification

Use the existing disposable PostgreSQL database ending in `_test`, with explicit
`TEST_DATABASE_URL` and `ALLOW_TEST_DATABASE_RESET=1`. No SQLite or real child data.
The full suite includes destructive migration tests: never point it at shared data.

From apps/backend after exporting the disposable test configuration:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest --cov=app --cov-report=term-missing
uv run --locked alembic heads
DATABASE_URL="$TEST_DATABASE_URL" MIGRATION_DATABASE_URL="$TEST_DATABASE_URL" uv run --locked alembic check
```

New tests cover the HTTP permission matrix, minimal projections, pagination and forged
cursors, missing-row semantics, validation and allowlists, rollback, consent separation,
and independent-connection concurrent creates/updates. Lock tests observe actual
PostgreSQL blocking for account/session/role/assignment/relationship/archive changes,
in both write-first and revocation-first order. Existing auth and migration tests remain.
