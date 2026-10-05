# Authentication and authorization foundation

This sprint adds authentication and action-scoped learner authorization to the same
FastAPI modular monolith and PostgreSQL database. It adds no registration, recovery,
user/role administration, content-processing, or consent-execution endpoints.

## Storage and migrations

`0005_auth_sessions` follows `0004_consent_evidence`. It creates only:

- `auth_sessions`: stable UUID session identity, user FK (`RESTRICT`), original
  authentication time, absolute and idle deadlines, revocation time/reason,
  UTC creation/update timestamps, and optimistic `row_version`.
- `auth_refresh_tokens`: UUID identity, session FK (`CASCADE`), unique SHA-256
  credential digest, generation, creation/expiry/consumption timestamps.

The existing nine tables and revisions 0001–0004 are unchanged. No account, password,
learner, consent, or research data is seeded. All models use the shared metadata.

Named checks validate timestamp order, digest length, nonnegative generations,
positive versions, paired revocation fields, and checked revocation reasons.
Unique constraints protect credential digests and `(session_id, generation)`.
A partial unique index permits at most one unconsumed credential per session.
Session indexes cover user lookup, active sessions, absolute expiry, and idle expiry.
The generation index also covers refresh-token lookup by session for cleanup.

Revocation retains consumed credentials so that replay can be detected. These are
expiring security credentials, not permanent audit records. Before deployment, arrange
scheduled deletion of sessions after their absolute deadline plus a short operational
retention period; deleting a session cascades its token digests. Do not delete consumed
generations while their session can still be used. No cleanup scheduler is added here.

## Passwords and login

Login accepts `login_handle` and password; email is neither used nor required.
Handles are stripped and lowercased consistently with the database convention.
Passwords are never stripped, case-folded, silently truncated, or stored as plaintext.

`pwdlib[argon2]` uses Argon2id with 64 MiB memory, three iterations, parallelism one,
and library-generated salts. Verification may upgrade an older supported Argon2id
hash after successful login. Unknown/missing/unrecognized hashes use dummy verification.
Disabled, anonymized, unknown, and incorrect-password attempts share one public error.
Account state and the observed password hash are rechecked under a user lock after
verification, before creating a session.

The hash helper requires 15–128 characters for new passwords. Login permits existing
passwords within a bounded request size. A compromised-password blocklist and accessible
provisioning process belong with future password creation/recovery; no such flow is
exposed in this sprint. No legacy plaintext or alternate hash algorithm is accepted.

Hash work runs in synchronous FastAPI workers. A nonblocking two-slot semaphore bounds
Argon2 memory use per process and returns `429` with `Retry-After: 1` at capacity.
This is NOT brute-force protection. Before public use, configure consistent per-source
and per-normalized-handle throttling at a trusted gateway/shared limiter, including
refresh abuse limits. School NATs, trusted proxy configuration, and non-enumerating
responses must be considered. There is no persistent account lockout or new Redis.

## Tokens and session lifecycle

- HS256 access JWTs live for five minutes. Claims are UUID `sub`, `sid`, and `jti`,
  exact issuer/audience, `token_type=access`, numeric `iat` and `exp`.
- The JWT header uses `typ=at+jwt`; validation fixes the algorithm independently of
  token input and rejects unexpected headers. There is no remote key lookup.
- JWTs contain no roles, learner lists, child content, or consent evidence.
- Refresh credentials use 32 random bytes, URL-safe encoding, and SHA-256 digest-only
  storage. They are never JWTs. Responses and request schemas conceal credentials in repr.
- Sessions expire absolutely after seven days, with a 24-hour idle deadline renewed
  only by refresh. The absolute deadline and original authentication time never move.
- Every protected request validates the JWT and reads current account, session, and
  active role state. Session expiry has no JWT clock-skew grace.

Mutation lock order is user -> session -> refresh credential. Queries refresh ORM
state after acquiring locks. Refresh consumes the old credential, flushes to release
its unique-current slot, inserts the replacement, and commits atomically. Access tokens
are returned only after commit. A failed transaction leaves the old credential usable.

Reusing any consumed credential of an active session revokes the entire session,
including the winner of concurrent refresh attempts. Revocation commits BEFORE the
`invalid_session` exception is raised. The mobile client must serialize refresh calls.
A lost refresh response can require signing in again; no replay grace period exists.

Logout accepts proof via a refresh credential, including a consumed generation, and
revokes only that session. It works without a valid access token. Unknown or already
revoked credentials return the same idempotent 204. A database failure returns 503.

`auth.service.revoke_all_sessions` is an internal transaction contract, not an endpoint.
Call it BEFORE mutating/flushing account credentials/status, then commit revocation and
the account change together. It obtains the user lock shared with login/refresh/logout.
Direct status updates deny access while disabled, but failing to revoke sessions could
revive them after reactivation. Future lifecycle operations must use this contract.

## Principal and module boundaries

`get_current_principal` returns a frozen, safe `Principal` with identity, active role
codes, active status, stable session identity, original authentication time, and token
context. Session ownership must match the JWT subject. Password hashes and refresh
digests never appear in the principal or `/me` response.

Auth owns passwords, JWTs, sessions, authentication dependencies, and global role guards.
Learners imports only the immutable auth contract and owns its relationship queries and
policy evaluation. Auth imports no learners models and performs no learner-table writes.
Any future multi-module lifecycle orchestration belongs above these modules, using
public services and one explicit transaction; no circular dependency is introduced.

The global learner/guardian/educator/administrator guards establish role eligibility
only. Future learner routes must resolve the principal on every request and call
`authorize_learner_action(db, principal, learner_id, action)`. Never construct a principal
from request fields, use token role claims, or cache grants across requests.

## Learner policy

| Actor/access | Allowed actions |
| --- | --- |
| Learner linked by learner_user_id | Basic profile, educational summary, read/update accessibility preferences, learning interaction |
| Guardian viewer | Basic profile, guardian-facing summary, read preferences |
| Guardian manager | Viewer permissions plus update accessibility preferences |
| Educator viewer | Limited basic profile, educational summary |
| Educator instructor | Viewer permissions plus learning interaction |
| Administrator alone | No learner content access |

Every path requires its matching active role. Guardian grants must match the actor and
learner and be unrevoked. Educator grants must also have `expires_at > current time`.
Archived profiles are denied. Creation provenance does not grant access. One complete
valid path suffices, but roles and relationships from different paths cannot be mixed.
An administrator who independently has a valid guardian relationship may use that
ordinary guardian path; the administrator role adds no child-data privilege.

The returned action-scoped grant includes an explicit basic-profile field allowlist.
Educators receive only id/display_name; self/guardians may additionally receive age_band
and grade_level. Future serializers must enforce the allowlist. Preference updates are
limited to the explicit accessibility field set in the learners service. These are
contracts; this sprint exposes no learner content or preference endpoints.

Unknown actions, unrelated actors, expired/revoked grants, missing learners, and archived
learners produce the same 404. Future nested resources must resolve learner ownership
from stored data; list filtering must occur before pagination/counts. Future writes must
recheck authorization in their transaction and coordinate locks with grant revocation.
A committed revocation affects subsequent checks; already-running reads are not canceled.

Role revocation immediately removes access through that role. Existing relationship rows
remain historical grants: future role-management operations must coordinate closing
corresponding relationships through learners services to prevent unintended access
restoration on reassignment. No role-management endpoint is included now.

Consent is deliberately separate: grants report `consent_evaluated=False`. Neither
recorded consent nor `can_provide_consent` grants access. Successful authorization does
not authorize consent-controlled processing. Future processing must separately evaluate
applicable consent/assent and fail closed until that evaluation is implemented.
Administrator elevation, MFA, emergency access, and audit workflows are not implemented;
there is no wildcard or elevated-content bypass.

## API and failure contract

| Endpoint | Result |
| --- | --- |
| POST /api/v1/auth/login | Handle/password -> access_token, refresh_token, token_type, expires_in |
| POST /api/v1/auth/refresh | refresh_token -> rotated pair |
| POST /api/v1/auth/logout | refresh_token -> 204 |
| GET /api/v1/auth/me | Bearer JWT -> user_id, login_handle, active status, current roles |

Responses use `Cache-Control: no-store`. Credentials are never placed in URLs or logs.
This is a first-party HTTP Bearer API, not a general OAuth authorization server.

Errors preserve `{ "error": { "code": "...", "message": "..." } }`:

- 401 invalid_credentials: unknown/disabled/anonymized account or invalid password.
- 401 authentication_required: missing/invalid/expired access token or unusable session.
  Includes `WWW-Authenticate: Bearer`.
- 401 invalid_session: invalid/expired/replayed refresh credential.
- 403 forbidden: missing required global role.
- 404 not_found: learner-specific denial without disclosing existence or grant status.
- 429 rate_limited with Retry-After: capacity rejection / limiter adapter contract.
- 422 validation_error: sanitized request validation without input echo.
- 503 service_unavailable: database failure without SQL/credential details.

## Configuration and local operation

Both `.env.example` files document configuration; no real `.env` is created or modified.
The runtime requires `JWT_SIGNING_KEY` with at least 32 bytes and rejects the example
placeholder. Generate a random key outside Git and inject it through deployment secrets.
Issuer defaults to `adaptive-assistant`, audience to `adaptive-assistant-api`.

| Setting | Default | Validation |
| --- | --- | --- |
| ACCESS_TOKEN_TTL_SECONDS | 300 | 30–300 |
| REFRESH_ABSOLUTE_TTL_SECONDS | 604800 | 300–604800 |
| REFRESH_IDLE_TTL_SECONDS | 86400 | 300–86400 |
| JWT_CLOCK_TOLERANCE_SECONDS | 30 | 0–30 |

Also require access TTL <= idle TTL <= absolute TTL. Signing settings use SecretStr;
validation strings conceal inputs. Alembic uses DatabaseSettings so migrations do not
require a runtime signing secret. Keep clocks synchronized. The current single-key
configuration does not implement overlapping key rotation: replacing the key invalidates
existing access JWTs; valid refresh sessions can obtain new ones. After key compromise,
revoke affected sessions as well. Never reuse production secrets in tests.

From `apps/backend`, with DATABASE_URL and a generated JWT_SIGNING_KEY exported:

```sh
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked alembic heads
uv run --locked alembic check
uv run --locked uvicorn app.main:create_app --factory --reload --no-access-log
```

A key can be generated into the current shell without writing a file:

```sh
export JWT_SIGNING_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

No users/passwords are seeded; account provisioning remains a later sprint. Existing
accounts can authenticate only with active status and valid Argon2id hashes.

## Verification and deployment limits

Use the existing dedicated PostgreSQL `_test` database and `ALLOW_TEST_DATABASE_RESET=1`.
The suite never falls back to DATABASE_URL. Migration tests are destructive; never use
shared data. Concurrency tests commit synthetic data through independent connections
and clean it up; do not run this suite with xdist.

```sh
# From repository root, after exporting the disposable TEST_DATABASE_URL:
export ALLOW_TEST_DATABASE_RESET=1
sh scripts/check_backend.sh
# From apps/backend:
uv run --locked pytest tests/integration/test_auth_concurrency.py -q
uv run --locked pytest tests/migrations -q
```

Tests cover hashing, token validation, safe failures, principal state, full action
matrix and negative isolation, session constraints, atomic rotation/replay, logout,
account revocation, consent separation, upgrades from base/0001/0004, and schema drift.

Before a public pilot, supply HTTPS, protected mobile credential storage, deployment
rate limiting, bounded session cleanup, restricted security logging, and operational
key handling. These deployment controls are not supplied by the local Compose setup.
No child data, clinical fields, or diagnosis logic is introduced.
