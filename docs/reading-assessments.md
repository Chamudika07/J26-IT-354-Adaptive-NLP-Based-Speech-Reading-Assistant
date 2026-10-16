# Instructor-observed reading assessments

This sprint adds educational reading observations to the existing FastAPI modular
monolith and PostgreSQL database. It does not diagnose dyslexia, grade its severity,
assign support bands, or compare children to age norms. Only `instructor_observed`
is supported. Learner self-assessment and guardian administration are unavailable.
There is no mobile, speech, OCR, NLP, audio, research export, or training capability.

## Material and evidence

`0006_reading_assessments` follows `0005_auth_sessions` without changing published
revisions or existing tables. It adds:

- `reading_assessment_materials`: immutable versioned content, administration
  instructions, word-count convention, and optional comprehension prompt/rubric.
  `(code, version)` is unique. Only availability, update timestamp, and row version
  may change. A new content, rubric, instruction, or tokenization revision needs a
  new material row/UUID. Retiring material blocks starts but preserves completion
  of already-bound sessions.
- `reading_assessment_sessions`: immutable learner, exact material UUID,
  administering user, collection mode, protocol version, and start time. The
  lifecycle is `started -> completed` or `started -> abandoned`. Both terminal
  states are immutable. One started session per learner/administering actor is
  permitted; different instructors may independently administer sessions.
- `reading_assessment_results`: one insert-only result per completed session.
  Raw observations, submitting actor, UTC submission time, and scoring version
  are retained. No duplicated learner/material ownership or derived metric columns.

UUID foreign keys use RESTRICT. All timestamps are timezone-aware and produced in
UTC. Session/material row versions use the shared SQLAlchemy version mixin.

The migration adds five triggers using four narrowly scoped PostgreSQL functions:
material immutability; session identity/terminal immutability; result immutability
and material/actor validation; and two deferred constraint triggers enforcing
exactly one result if and only if the session is completed. Deferred checks permit
result insertion followed by session completion in one transaction. Counts,
nullability, uniqueness, state timestamps, and foreign keys also have constraints.
No event-count reconciliation equality is imposed.

Material and session DELETEs, and result UPDATEs/DELETEs, are rejected. There is no
public correction or deletion API. Future corrections require a separate,
attributable supersession design. Retention/erasure requires a reviewed privileged
workflow and must not be interpreted as permission to retain child data indefinitely.
Production application roles must not own tables or have TRUNCATE/trigger-disabling
privileges. Migration/test roles are necessarily more privileged.

No production material is seeded. The catalog starts empty until approved original
or appropriately licensed material is published through a separately reviewed
internal process. That process must verify word_count using the declared versioned
counting convention. Synthetic original passages exist only in automated tests.
Age/grade metadata and textbook collections are not added.

## Public API

All six routes require current authentication and return `Cache-Control: no-store`.

| Method/path (under /api/v1) | Behavior |
| --- | --- |
| GET /assessment-materials | Active summaries; educator role and at least one current instructor relationship to a nonarchived learner |
| POST /learners/{learner_id}/reading-assessments | Start using material_id; 201 and bound administration material |
| GET /learners/{learner_id}/reading-assessments | Authorized history, without administration material |
| GET /learners/{learner_id}/reading-assessments/{assessment_id} | Authorized summary; full material only for the administering user with current instructor access |
| POST /learners/{learner_id}/reading-assessments/{assessment_id}/complete | Strict observations and row_version; 200 |
| POST /learners/{learner_id}/reading-assessments/{assessment_id}/abandon | row_version only; 200 |

Start accepts only material_id. The server binds `instructor_observed`,
`reading-observation-v1`, the principal's user ID, and current time. Neither complete
nor abandon accepts actor, learner, material, protocol, or scoring identity fields.
Unknown request fields are forbidden. Core counts are required strict nonnegative
integers; duration and row_version are strictly positive integers. All integer
inputs are bounded to PostgreSQL INTEGER's positive range, without a clinical claim.

The completion fields are reading_duration_ms, attempted_word_count,
correct_word_count, omission_count, substitution_count, insertion_count,
repetition_count, self_correction_count, optional unfamiliar_word_count, and the
comprehension pair. Null unfamiliar count means unmeasured, not zero.
When the material has questions, comprehension is required for its entire fixed
question set and total must equal the material's question count. Otherwise both
comprehension fields must be null. Raw answers and free-text learner notes are absent.

Public responses exclude actor IDs, relationship IDs, auth-session IDs, account
linkage, and consent evidence. Material UUIDs identify exact versions. Only start
and the administering instructor's authorized detail include passage, instructions,
questions, rubric, and tokenization version. Summary/history/catalog models exclude
these fields; no role or broad model serialization can accidentally add them.

History is ordered by started_at DESC, id DESC, scoped by authorized learner before
pagination. Default limit is 25, maximum 100; there is no total count. The cursor is
`UTC-ISO-timestamp|UUID`, a position, never an authorization capability. An arbitrary
valid cursor cannot widen learner scope. Catalog pagination uses ascending UUIDs.
Neither collection is a frozen snapshot; authorization is checked on every request.

## Authorization and transactions

Learners owns four new actions: reading_assessment.read, reading_assessment.start,
reading_assessment.submit, and reading_assessment.abandon. Self, guardian viewer/
manager, and educator viewer/instructor can read a related learner's summary.
Only educator instructors may write, and only the session's administering actor
may complete or abandon. Administrator alone has no child-data access. Multiple
roles never combine with mismatched relationships. Educator viewer reads are
intentional; instructor access is required for every assessment write.

The learners public contracts authorize_learner_action_for_write and
assert_protected_learner_action_live protect learner/grant access and recheck expiry.
They do not commit or write auth tables. Callers first protect auth state. Assessments
imports no learner relationship models and calls no private learner helpers.

Mutation lock order is user -> auth session -> roles/assignments -> learner ->
supporting relationship -> assessment session (or material for start). Guardian
relationships encountered before an instructor path follow the existing ordering.
Educator relationship SHARE locks prevent revocation until commit. Parent learner
locks protect archive/link changes and serialize duplicate start checks. Current
principal deadlines and educator expiry are rechecked after domain-lock waits.

Complete verifies ownership, status, and row_version, validates against the exact
material, inserts the result, and performs a versioned ORM state change, then commits
once. No partial result survives failure. The response is built explicitly and
returned only after commit. Concurrent terminal commands yield one winner and one
409. Duplicate completion is a conflict even for identical payloads; GET resolves a
lost response. Stale versions are not automatically retried. No result-edit endpoint
or in-place evidence correction exists.

| Failure | Status/code |
| --- | --- |
| Missing/invalid/expired authentication | 401 authentication_required |
| Ineligible global material catalog | 403 forbidden |
| Inaccessible/missing learner/session, wrong administrator, inactive/unknown start material | 404 not_found |
| Already terminal | 409 assessment_state_conflict |
| Duplicate active start | 409 assessment_start_conflict |
| Stale row version | 409 version_conflict |
| Invalid body/query/measurements | 422 validation_error |
| Unexpected database failure or unavailable historical calculator | 503 service_unavailable |

Errors use the existing fixed sanitized envelope. Both learner_id and assessment_id
constrain nested lookups. No request values, actor identities, constraint names,
relationship status, observation payloads, or child content belong in error/log output.

## Frozen observation and scoring protocol

`reading-observation-v1` defines:

- Presented words: the exact material's stored word count.
- Attempted words: distinct source-word positions attempted, excluding skipped
  positions, inserted words, and repeated attempts.
- Correct words: attempted positions ultimately read correctly under the material's
  instructions, including accepted self-corrections.
- Omissions: skipped positions within the portion reached. Unread trailing text is
  not automatically an omission. Attempted + omissions cannot exceed presented.
- Substitutions, insertions, repetitions, self-corrections: observed event counts.
  They can overlap; their sum need not equal attempted minus correct.
- Unfamiliar words: distinct attempted positions explicitly identified as unfamiliar,
  not inferred from errors. If measured, this cannot exceed attempted words.
- Duration: instructor-measured reading time only, in milliseconds, excluding
  instructions/comprehension. Session timestamps are not reading-duration measures.
  A reading interrupted outside the material's protocol should be abandoned/restarted.

`reading-scoring-v1` preserves these factual formulas (D milliseconds, A attempted,
C correct, R comprehension correct, Q total):

| Public value | Formula |
| --- | --- |
| reading_duration_seconds | D / 1000 |
| reading_time_minutes | D / 60000 |
| attempted_words_per_minute | A * 60000 / D |
| words_correct_per_minute | C * 60000 / D |
| attempted_word_accuracy_percentage | C * 100 / A, null when A=0 |
| incorrect_attempt_percentage | (A-C) * 100 / A, null when A=0 |
| comprehension_percentage | R * 100 / Q, null when absent |

D must be positive. A=0 gives zero WPM/WCPM and null accuracy/error percentages.
Counts must satisfy 0 <= C <= A; comprehension requires 0 <= R <= Q. Incorrect-attempt
percentage excludes omissions, so the omission count remains visible. WPM counts
source positions, not every spoken token; no normative comparison is implied.

Calculation uses a local Decimal context and rounds only final values to two decimal
places with ROUND_HALF_UP. Public decimal values serialize as strings. Raw values
and scoring version are persisted; derived values are computed on demand. Unknown
versions fail closed. Future calculators must retain v1 unchanged and dispatch by
version instead of silently recalculating old evidence with new rules.

Material version, counting convention, protocol, raw observations, actors, UTC times,
and scoring version reproduce the calculation. Aggregate data cannot independently
re-adjudicate each reading event; this is an explicit data-minimization tradeoff.
No automatic "initial baseline" selection or adaptation is implemented. A later
policy may select the first valid completed assessment while retaining reassessments.

## Consent and verification

Authentication, learner authorization, and processing consent remain separate.
Authorization grants retain consent_evaluated=False. Consent evidence never grants
access. Ordinary educational assessment does not infer research/audio permission.
No research export, audio collection, or training exists. A deployment requiring
additional learning-support consent needs that separate policy implemented before
use with real children. Retention, material approval, and deployment least privilege
remain prerequisites for real-child use.

Use the existing guarded disposable PostgreSQL fixture: explicit TEST_DATABASE_URL
ending in _test and ALLOW_TEST_DATABASE_RESET=1. Concurrency tests use independent
committed connections, observe actual PostgreSQL blocking, and cover competing
terminal commands, starts, authority revocation, and deadlines after lock waits.
Migration tests cover 0005 upgrade, downgrade/re-upgrade, a single head, metadata
checks, constraints, and triggers. Test cleanup TRUNCATE is privileged and restricted
to the exclusive disposable database. Never run this suite on shared data.
