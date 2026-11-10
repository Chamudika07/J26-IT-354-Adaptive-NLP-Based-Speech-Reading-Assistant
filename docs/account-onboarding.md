# Component 1: managed account and learner onboarding

This extends the existing authentication foundation. Administrators can now create
educator accounts and learner profiles, assign instructor/viewer access, and revoke
assignments through Swagger. There is no public self-registration or public admin
creation endpoint. Use only synthetic learner data for local development and demos.

## 1. Start the current backend / අලුත් API endpoints load කරන්න

From the repository root, using the existing local configuration:

```sh
docker compose config --quiet
docker compose up --build -d --wait
docker compose exec backend alembic current
docker compose exec backend alembic heads
```

The image must be rebuilt to include these endpoints. Existing named PostgreSQL
storage is preserved. Never use `down -v` or change the existing database password
to resolve an authentication error. Do not print resolved Compose configuration.

This feature has no schema changes. Both revision commands should report
`0009_ocr_review_workflow`. If they do not match, stop and review migration state
before onboarding. This guide does not automatically apply migrations.

Swagger: <http://127.0.0.1:8000/docs> with the default API port. It is enabled only
for `APP_ENV=development` or `test`. For the previously inspected local setup,
PostgreSQL is mapped to host port 5433; Compose backend connections use `db:5432`.

## 2. First local administrator / මුල් administrator account එක

Run once, interactively, against your intended **local development database**:

```sh
docker compose exec backend python -m app.modules.auth.bootstrap --confirm-local-development
```

Enter a login handle, then a private password of 15–128 characters twice. Passwords
are entered through a hidden prompt, not command arguments or a shared JSON file.
Keep the credentials in your password manager. The command prints only the new user
UUID and sign-in instructions. It requires `APP_ENV=development` and never runs at
startup. No default credentials are included.

The first administrator grant is self-attributed. Any existing administrator grant,
including revoked historical assignments, prevents another bootstrap. An existing
login handle is never overwritten or elevated. Concurrent bootstrap attempts create
at most one administrator. If bootstrap refuses because an administrator already
exists, use that account; credential recovery is outside this feature.

Host alternative, from `apps/backend` with the intended local `DATABASE_URL`,
`JWT_SIGNING_KEY`, and `APP_ENV=development` already configured:

```sh
uv run --locked python -m app.modules.auth.bootstrap --confirm-local-development
```

## 3. Administrator login / Swagger Authorize

Use `POST /api/v1/auth/login` with your new administrator handle/password. Paste the
returned `access_token` alone into Swagger **Authorize** (without a `Bearer ` prefix).
Check `GET /api/v1/auth/me`: roles should include `administrator`.

Do not project passwords or token responses during presentations. Access tokens
normally last five minutes; sign in again and replace the Swagger token if needed.

## 4. Create an educator

While authorized as administrator, use `POST /api/v1/auth/users`:

```json
{
  "login_handle": "demo.educator",
  "password": "<replace with your private 15-128 character passphrase>"
}
```

Expected: HTTP 201 with `user_id`, normalized `login_handle`, `status: active`, and
`roles: ["educator"]`. Save the returned educator UUID. Password hashes and tokens
are never returned. No email or child details are requested.

The server selects the educator role. Client-supplied role, status, grantor, or
verification fields are rejected. Duplicate handles return HTTP 409, including
case/whitespace-equivalent handles and concurrent submissions. User creation and
role assignment commit together or both roll back.

## 5. Create a synthetic learner

Use `POST /api/v1/learners` as administrator:

```json
{
  "display_name": "Synthetic Demo Reader"
}
```

Expected: HTTP 201 with `id` and `display_name`. Save the learner UUID. This creates
a login-less profile; it does not create a child account, collect consent, or grant
the administrator access to the learner's reading content.

## 6. Assign instructor access / learner permission දෙන්න

Generate a future UTC expiry (no database change):

```sh
python3 -c 'from datetime import datetime, timedelta, UTC; print((datetime.now(UTC) + timedelta(days=7)).isoformat())'
```

Use `POST /api/v1/learners/{learner_id}/educator-grants` as administrator:

```json
{
  "educator_user_id": "<educator UUID from step 4>",
  "access_level": "instructor",
  "expires_at": "<future UTC timestamp>"
}
```

Expected: HTTP 201. Save the returned grant `id` for revocation. The educator must
be active with an active educator role; the learner must exist and not be archived.
`viewer` permits existing educator reads, while `instructor` also permits existing
reading-material, PDF and assessment writes. Neither allows preference access.

Expiry is required, timezone-aware, normalized to UTC, and checked against database
time after locking. An existing unrevoked assignment blocks another assignment,
even if expired. Revoke it explicitly before replacing it; history is preserved.

## 7. Test as educator

Log in with the educator credentials. Replace the Swagger authorization token with
the educator token, then call:

1. `GET /api/v1/auth/me` — educator role.
2. `GET /api/v1/learners` — the assigned synthetic learner.
3. `GET /api/v1/learners/{learner_id}` — permitted profile.
4. `POST /api/v1/learners/{learner_id}/reading-materials`:

```json
{
  "title": "Synthetic demo story",
  "language_tag": "en",
  "text": "A cat sits on a mat. The sun is warm."
}
```

Save `id` as material ID and `latest_revision.id` as revision ID. Then call:

```text
POST /api/v1/learners/{learner_id}/reading-materials/{material_id}/revisions/{revision_id}/processing-runs
```

Body: `{}`. Expect HTTP 201 and `status: succeeded` for a new processing run.
These actions create synthetic application records. PDF operations still require
private storage setup, and assessment sessions still require separately provisioned
assessment materials. This feature adds neither OCR execution nor assessment seeds.

## 8. Revoke access

Switch back to the administrator token and call, without a request body:

```text
POST /api/v1/learners/{learner_id}/educator-grants/{grant_id}/revoke
```

Expected: HTTP 200 with `revoked_at`. Repeating the same revocation returns the same
decision without changing its original actor/time. Existing educator tokens lose
that learner access on subsequent requests. A grant under another learner ID is
not found. After revocation, a new assignment gets a new UUID.

## Contract and architecture

| Condition | Result |
| --- | --- |
| Missing/invalid authentication | 401 |
| Authenticated non-administrator management request | 403 |
| Invalid input, educator or expiry | 422 |
| Missing/archived learner or mismatched grant | 404 |
| Duplicate handle or open educator grant | 409 |
| Unavailable required role | 409 |
| Database operation failure | Sanitized 503 |

Auth owns accounts and role grants. Learners owns profiles and educator grants and
uses auth public contracts for administrator and target-educator validation. No
module writes another module's tables. Each service owns its shared transaction
and rolls back on failure. Identity/role/session authorization is rechecked under
locks. User locks are ordered before session/role and learner/relationship locks;
revocation shares the learner-first domain lock order with existing content writes.

New management powers do not bypass existing learner-content authorization.
Onboarding does not establish guardian authority, consent or clinical status.
There is no account listing, password reset, arbitrary role assignment, guardian
onboarding, or additional administrator creation HTTP API in this version.

For a real pilot, separately review identity verification, recovery, compromised
password screening, rate limiting and operational administrator governance before
using real learner information. Existing local testing is synthetic only.

## Verification

Use `scripts/check_backend.sh` with an explicitly configured **disposable** PostgreSQL
database ending in `_test` and `ALLOW_TEST_DATABASE_RESET=1`. The full test suite
includes destructive migration tests; never point it at the development application
database. New tests cover the onboarding-to-text-processing flow, authorization,
validation, grant expiry/revocation, rollback, duplicate races and bootstrap guards.
