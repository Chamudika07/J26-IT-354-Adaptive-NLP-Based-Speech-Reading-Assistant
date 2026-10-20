# Component 2 integration audit — 2026-10-20

The current implementation passes the available offline checks after focused fixes.
An authenticated end-to-end demo and live Gemini remain unverified. This audit
does not establish production readiness.

Branch: `feat/component-2-simplification`. At entry there were no tracked-file
modifications, but the mobile implementation, TypeScript client, root package
manifest, pnpm workspace manifest, and pnpm lockfile were untracked. They were
preserved. No commit, push, merge, branch switch, migration edit, database reset,
account provisioning, or provider-configuration change was performed.

The audit modifies two Component 2 backend implementation files, three backend
test files, and the mobile/API-client READMEs. Changes within the pre-existing
untracked implementation cover `App.tsx`, mobile session/environment configuration,
`.env.example`, the mobile test script, and the decimal response contract. New
artifacts are the mobile regression tests and this report. Components 1, 3, and 4
were not edited. Subsequent authentication work added Expo SecureStore to the
mobile dependencies and updated the pnpm lockfile.

| Journey | Evidence and limits |
| --- | --- |
| Enter passage, select level/strategy, simplify | Four levels and five strategies match backend enums. Empty/oversized inputs are rejected. Callback tests verify the selected values, learner URL context, and returned result/vocabulary. |
| Read result and vocabulary | The screen displays simplified text, vocabulary definitions/synonyms, optional examples, and warnings. Synthetic responses exercise the display callbacks. |
| Request word explanation | Uses the current learner ID, selected term, optional example as context, and returned **simplification** session ID. A successful explanation is displayed for the active term. |
| Close/switch a pending explanation | Existing AbortController handling was already correct for close/switch. Regression tests resolve/reject cancelled requests late and verify they cannot replace the active state. |
| Submit feedback | `too_hard`, `just_right`, `too_easy`, and `skipped` are exercised. Each uses the same learner and simplification session; `skipped` sends `completed_reading=false`. The backend keeps feedback append-only. |
| Error paths | Backend API tests cover missing authentication, mocked authorization denial, invalid requests, rate limits, unavailable/malformed providers, and database errors. Mobile tests cover 401/403/404/422/429/503 envelopes, Retry-After, network failure, retry, abort distinction, refresh-token rotation, concurrent refresh coordination, and failed-session clearing. |
| Reset and start again | Reset, new simplification, and session Apply/Clear now invalidate pending requests and clear prior result, vocabulary, explanation, feedback, errors, and loading state. Apply/Clear also removes the passage. Result Reset retains the editable input and chosen options. |
| Identity consistency | Learner IDs are in endpoint paths. Explanation includes the simplification session ID in its body; feedback includes it in its path. Backend ownership lookup filters both learner and session ID. Authentication-session IDs are separate and are not used as reading-session IDs. |

Authorization is enforced before Component 2 provider execution and session
lookup. Unauthorized learner/session access deliberately returns the same 404 as
a missing resource. Shared authentication validates JWTs and checks persisted
session/user state and current roles. Actual expired/revoked-session database
behavior and the learner policy matrix were inspected but not exercised against
PostgreSQL in this run.

The frontend tests use a lightweight hook harness and mock native elements, with
the actual App callbacks and fetch client transpiled using the existing TypeScript
dependency. They do not render React Native controls, exercise React scheduling,
or prove behavior on a physical device. Backend API tests use existing dependency
overrides; they do not prove live authenticated database integration.

Confirmed defects and fixes:

1. **Stale mobile state across requests and identity changes.** A new simplify
   request left the old result visible, Reset did not invalidate feedback, and
   Apply/Clear left old learner results and pending operations alive. Added
   cancellation and stale-result guards for simplification and feedback, a shared
   reading-state reset, and unmount cancellation. Existing explanation
   cancellation is retained. Submission now requires both learner ID and token.
   Cancellation prevents local stale state; it cannot undo a server write that
   already completed.
2. **Provider/database concept mismatch.** `SimplificationAIResult.to_dict()`
   emits a list for `concepts_preserved`, while the existing PostgreSQL column is
   Boolean. Both empty and populated lists fail SQLAlchemy's real PostgreSQL bind
   conversion. The service now persists `None` for that nullable assessment.
   A generated list of labels is not a validated boolean judgment. No schema
   change or new assessment algorithm was introduced.
3. **Malformed provider values escaped validation.** Whitespace-only text and
   vocabulary fields, oversized output, invalid difficulty range/precision, and
   blank language tags could pass provider parsing and fail later. Added bounded
   output/difficulty validation and nonblank field checks inside the provider's
   existing sanitized `ProviderResponseError` boundary. Nine offline regressions
   exercise these cases. Existing route tests verify that this exception maps to
   503.
4. **Public bundle credential path.** Environment configuration read
   `EXPO_PUBLIC_DEV_ACCESS_TOKEN` and initialized the session from it. Such a value
   can enter an exported bundle; keeping subsequent runtime state in memory does
   not prevent that. Removed public token/learner initialization and its example
   configuration. Manual session entry remains: access tokens stay in memory and
   rotating refresh tokens use Expo SecureStore. The local mobile dotenv file
   contained only the public base-URL variable; no credential exposure was
   established by this audit.
5. **Decimal contract mismatch.** Pydantic serializes the output difficulty
   Decimal as a JSON string, while TypeScript declared a number. Corrected the
   response type and added a wire-format assertion (`"0.25"`) to the API test.
6. **Stale documentation.** Mobile and API-client READMEs still described empty
   placeholders. They now describe the actual implementation and its limitations,
   including the handwritten client contracts.

Validation commands and observed results follow. `root` means the repository
root; commands using `uv` ran from `apps/backend`.

| Directory | Exact command | Observed result |
| --- | --- | --- |
| root | `pnpm typecheck` | Passed before and after fixes, both workspace packages. |
| apps/backend | `uv run --locked ruff check .` | Passed before and after fixes. |
| apps/backend | `uv run --locked ruff format --check .` | Passed before and after fixes; 99 files formatted. |
| apps/backend | `uv run --locked mypy` | Passed before and after fixes; 66 source files. |
| apps/backend | `env -u TEST_DATABASE_URL -u ALLOW_TEST_DATABASE_RESET uv run --locked pytest --cov=app --cov-report=term-missing` | Initial: 371 passed, 287 skipped, one warning; 81% total coverage. |
| apps/backend | `env -u TEST_DATABASE_URL -u ALLOW_TEST_DATABASE_RESET uv run --locked pytest --cov=app --cov-report=term-missing -q -rN` | Final: 382 passed, 287 skipped, one warning; 82% total coverage. Includes all Component 2 unit/API/Gemini tests and shared auth unit tests. |
| apps/backend | `env -u TEST_DATABASE_URL -u ALLOW_TEST_DATABASE_RESET uv run --locked pytest tests/unit/test_simplification_service.py -k provider_concepts -q` | Before fix: two expected regression failures, both a list rejected by the PostgreSQL Boolean binder. |
| apps/backend | `env -u TEST_DATABASE_URL -u ALLOW_TEST_DATABASE_RESET uv run --locked pytest tests/unit/test_simplification_service.py -q` | After persistence fix: 47 passed. |
| apps/backend | `env -u TEST_DATABASE_URL -u ALLOW_TEST_DATABASE_RESET uv run --locked pytest tests/unit/test_simplification_gemini.py -k invalid_ -q --tb=no` | Before validation fix: nine expected regression failures and one existing pass. Final full suite passes these regressions. The language-tag fixture was narrowed to whitespace to match the actual shared schema. |
| root | `node --test apps/mobile/tests/component2.test.cjs` | During test authoring: first a harness path error, then 14 passed/5 failed due to a selector and incomplete feedback fixtures; after harness corrections, 19 passed. Ten additional cases are included in the current follow-up below. |
| root | `pnpm --filter @readbuddy/mobile test` | Current follow-up: all 29 callback, transport, secure-storage, and refresh regressions passed. |
| apps/mobile | `pnpm exec expo-doctor` | Passed all 21 checks. |
| apps/mobile | `pnpm exec expo export --help` | Confirmed available installed-CLI export options; no existing export script was present. |
| apps/mobile | `env EXPO_NO_DOTENV=1 pnpm exec expo export --platform ios --platform android --output-dir /tmp/readbuddy-component2-audit-before` | Initial Android and iOS Hermes bundles exported successfully. |
| apps/mobile | `env EXPO_NO_DOTENV=1 pnpm exec expo export --platform ios --platform android --output-dir /tmp/readbuddy-component2-audit-after` | Final Android and iOS Hermes bundles exported successfully. |
| root | `git diff --check` | Passed for tracked edits. |

The targeted Ruff formatting command was:
`uv run --locked ruff format app/modules/simplification/provider/gemini.py app/modules/simplification/service.py tests/api/test_simplification_api.py tests/unit/test_simplification_gemini.py tests/unit/test_simplification_service.py`
(one file reformatted). The backend validation script was inspected and its
check commands run individually with locked dependencies; its `uv sync` step was
not needed during the original audit. Later automatic-refresh work added Expo
SecureStore and updated the pnpm lockfile.

`TEST_DATABASE_URL` was not configured. Test invocations explicitly removed both
database-test variables to honor the prohibition on resets. All 287
PostgreSQL-dependent cases were skipped, including **53 learner authorization
cases**. No production/development URL was substituted and no database was reset.
Existing PostgreSQL fixtures insert synthetic accounts/consent evidence, so those
fixtures were not executed. Full persisted authorization/consent behavior remains
unverified. The test warning concerns Starlette's deprecated httpx TestClient
integration; bundle warnings concern NO_COLOR/FORCE_COLOR. Neither check failed.

Security and consent findings:

- `LearnerAuthorization.consent_evaluated` is still explicitly `Literal[False]`.
  An access grant does not represent consent to process learner content.
- `_source_text_for_retention()` still unconditionally returns `None`.
  Component 2 does not store the raw input in `source_text`; it does persist its
  hash/length, generated simplified text, vocabulary, and feedback. Generated text
  can repeat information from the input, so this is not a claim that all source
  information disappears.
- Consent evidence models (`consent_records`, `consent_notice_versions`) exist.
  No shared consent-evaluation service or public consent query was found.
- Gemini's request construction includes the full source passage for
  simplification and the selected term/context for explanations. **Not retaining
  raw source text does not prevent external transmission.** The current execution
  path does not evaluate consent before sending to an enabled provider.
- The local backend provider remains `disabled`; no provider configuration was
  changed. Gemini tests use `httpx.MockTransport`; no live Gemini call was made.
- No credentials, learner accounts, or consent records were created, and no
  learner/child data was sent externally. Local configuration was inspected only
  through variable names and the allowlisted provider name.

Remaining demo blockers are the missing shared consent interface, an approved
synthetic authenticated account with an authorized learner relationship, and
database/device integration verification. The mobile screen has manual session
entry rather than a login form, but it now securely retains the refresh session,
rotates refresh tokens, coordinates concurrent refreshes, and retries an
authenticated Component 2 request once. Shared routes provide login/refresh and
authorized learner reads, but no account/learner provisioning flow was found.
No suitable live account was supplied or verified; the audit did not query
application data to discover one. The disabled provider also prevents successful
live simplification/explanation. Live Gemini compatibility and output quality
remain untested.

The single best next action is to coordinate with the shared backend owner on a
reviewed consent-evaluation interface and approved synthetic learner demo setup.
Then connect Component 2 to that interface and run the authenticated device flow
in an isolated environment before considering external-provider testing.
